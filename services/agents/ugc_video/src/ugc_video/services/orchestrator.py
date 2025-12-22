"""
Orchestration Service
Manages multi-agent workflows and integrates with S3 and database
"""
import os
import uuid
import tempfile
from typing import List, Optional
from pathlib import Path
from loguru import logger
from crewai import Task, Crew
import langsmith
from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.conversation import Conversation, Message, MessageRole, UGCType
from ..models.artifact import Artifact, ArtifactType
from ..services.storage import S3StorageService
from ..services.crew_agents import (
    create_chat_agent,
    create_prompt_agent,
    create_image_generator_agent,
    create_script_agent,
    create_video_agent,
)


class UGCOrchestrator:
    """Orchestrates UGC generation workflows with S3 and database integration."""

    def __init__(
        self,
        db_session: AsyncSession,
        storage_service: S3StorageService,
        conversation_id: uuid.UUID,
        tenant_id: str,
        user_id: str
    ):
        self.db_session = db_session
        self.storage_service = storage_service
        self.conversation_id = conversation_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.settings = get_settings()
        self.temp_dir = tempfile.mkdtemp(prefix="ugc_")

    async def generate_ugc_images(
        self,
        person_image_bytes: bytes,
        product_image_bytes: Optional[bytes],
        screenshot_bytes: Optional[bytes],
        logo_bytes: Optional[bytes],
        base_intent: str,
        ugc_type: UGCType
    ) -> List[str]:
        """
        Generate 4 diverse UGC images using 2-agent sequential workflow.
        
        Returns:
            List of S3 keys for generated images
        """
        # Save uploaded files to temp directory
        person_image_path = os.path.join(self.temp_dir, "person_image.jpg")
        with open(person_image_path, "wb") as f:
            f.write(person_image_bytes)

        product_image_path = None
        screenshot_path = None
        logo_path = None

        if product_image_bytes:
            product_image_path = os.path.join(self.temp_dir, "product_image.jpg")
            with open(product_image_path, "wb") as f:
                f.write(product_image_bytes)

        if screenshot_bytes:
            screenshot_path = os.path.join(self.temp_dir, "screenshot.jpg")
            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)

        if logo_bytes:
            logo_path = os.path.join(self.temp_dir, "logo.jpg")
            with open(logo_path, "wb") as f:
                f.write(logo_bytes)

        if not base_intent:
            base_intent = "A person showcasing a product in a natural, engaging way"

        # Create agents
        prompt_agent = create_prompt_agent()
        image_agent = create_image_generator_agent(ugc_type.value)

        # Task 1: Generate 4 prompts
        task1 = Task(
            description=f"""Generate 4 diverse UGC prompts.

Base intent: "{base_intent}"

Call the "UGC Prompt Variator" tool ONCE with this base_intent.
The tool will return 4 prompts. 

After receiving the prompts, your task is complete. Output the 4 prompts clearly.""",
            expected_output="4 diverse UGC prompts clearly listed and numbered 1-4",
            agent=prompt_agent,
            human_input=False
        )

        # Task 2: Generate 4 images
        task2_description = f"""The previous task provided 4 prompts. You must generate 4 images, one for each prompt.

Person image: {person_image_path}
"""
        
        if ugc_type == UGCType.PHYSICAL_PRODUCT:
            task2_description += f"Product image: {product_image_path}\n"
        elif ugc_type == UGCType.DIGITAL_PRODUCT:
            task2_description += f"Screenshot: {screenshot_path}\n"
        elif ugc_type == UGCType.SERVICE:
            if logo_path:
                task2_description += f"Logo: {logo_path}\n"

        task2_description += """
Your task is to make 4 separate tool calls. After each successful call, move to the next one.

STEP 1: Generate first image
- Use the FIRST prompt from the previous task
- Set output_filename to "generated_ugc_image_1.png"
- Wait for success confirmation

STEP 2: Generate second image  
- Use the SECOND prompt from the previous task
- Set output_filename to "generated_ugc_image_2.png"
- Wait for success confirmation

STEP 3: Generate third image
- Use the THIRD prompt from the previous task
- Set output_filename to "generated_ugc_image_3.png"
- Wait for success confirmation

STEP 4: Generate fourth image
- Use the FOURTH prompt from the previous task
- Set output_filename to "generated_ugc_image_4.png"
- Wait for success confirmation

After completing all 4 steps, report: "Successfully generated 4 images: generated_ugc_image_1.png, generated_ugc_image_2.png, generated_ugc_image_3.png, generated_ugc_image_4.png"

CRITICAL: The output_filename MUST change for each call (1, 2, 3, 4). Do not repeat filenames.
Always pass ugc_type parameter to the tool."""

        task2 = Task(
            description=task2_description,
            expected_output="Confirmation message listing all 4 generated image files",
            agent=image_agent,
            human_input=False,
            context=[task1]
        )

        # Execute crew
        crew = Crew(
            agents=[prompt_agent, image_agent],
            tasks=[task1, task2],
            verbose=True,
            process="sequential",
            full_output=False
        )

        logger.info("Starting 2-Agent Sequential Workflow for image generation")
        result = crew.kickoff()
        logger.info(f"Image generation workflow completed: {result}")

        # Find generated images and upload to S3
        generated_s3_keys = []
        for i in range(1, 5):
            local_filename = f"generated_ugc_image_{i}.png"
            local_path = os.path.join(self.temp_dir, local_filename)
            
            if os.path.exists(local_path):
                # Upload to S3
                s3_filename = f"ugc_image_{self.conversation_id}_{i}.png"
                s3_key = await self.storage_service.upload_file(
                    file_content=open(local_path, "rb"),
                    tenant_id=self.tenant_id,
                    conversation_id=str(self.conversation_id),
                    artifact_type="image",
                    filename=s3_filename,
                    content_type="image/png"
                )
                generated_s3_keys.append(s3_key)

                # Create artifact record
                artifact = Artifact(
                    conversation_id=self.conversation_id,
                    artifact_type=ArtifactType.IMAGE,
                    s3_key=s3_key,
                    s3_url=self.storage_service.generate_presigned_url(s3_key),
                    metadata={
                        "variant_index": i,
                        "ugc_type": ugc_type.value,
                        "generated_from": "banana_ugc_tool"
                    }
                )
                self.db_session.add(artifact)

        await self.db_session.commit()
        logger.info(f"Generated {len(generated_s3_keys)} images and uploaded to S3")

        return generated_s3_keys

    async def generate_ugc_video(
        self,
        image_s3_key: str,
        product_name: str,
        tone: str,
        platform: str,
        ugc_type: UGCType
    ) -> tuple[str, Optional[str]]:
        """
        Generate UGC video script and video using 2-agent sequential workflow.
        
        Returns:
            Tuple of (script_text, video_url)
        """
        # Download image from S3 to temp file
        image_bytes = await self.storage_service.download_file(image_s3_key)
        image_path = os.path.join(self.temp_dir, "reference_image.png")
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Create agents
        script_agent = create_script_agent(ugc_type.value)
        video_agent = create_video_agent()

        # Task 1: Generate script
        task1 = Task(
            description=f"""Generate an 8-second UGC video script.

Call the "UGC Script Maker" tool with these parameters:
- ugc_image_reference: {image_path}
- product_name: {product_name}
- tone: {tone}
- platform: {platform}
- ugc_type: {ugc_type.value}

Return the complete script.""",
            expected_output="Complete 8-second UGC video script",
            agent=script_agent,
            human_input=False
        )

        # Task 2: Generate video
        task2 = Task(
            description=f"""Generate a UGC video using Veo-3.1.

The previous task generated a script. Use that script to create the video.

Call the "Veo3.1 Image-to-Video Generator" tool with:
- image_reference: {image_path}
- script_text: [Use the script from the previous task]
- duration_seconds: 8

Wait for the video generation to complete and return the video URL.""",
            expected_output="Video URL from Veo-3.1 generation",
            agent=video_agent,
            human_input=False,
            context=[task1]
        )

        # Execute crew
        crew = Crew(
            agents=[script_agent, video_agent],
            tasks=[task1, task2],
            verbose=True,
            process="sequential",
            full_output=False
        )

        logger.info("Starting 2-Agent Sequential Workflow for video generation")
        result = crew.kickoff()
        logger.info(f"Video generation workflow completed: {result}")

        # Parse result to extract script and video URL
        result_str = str(result)
        script = ""
        video_url = None

        # Extract video URL if present
        if "Video generated successfully:" in result_str or "✅ Video generated successfully:" in result_str:
            if "✅ Video generated successfully:" in result_str:
                parts = result_str.split("✅ Video generated successfully:")
            else:
                parts = result_str.split("Video generated successfully:")
            
            if len(parts) > 1:
                url_part = parts[1].strip()
                url_part = url_part.split("[VIDEO_GENERATION_COMPLETE]")[0].strip()
                video_url = url_part.split()[0] if url_part else None
                script = parts[0].strip()
        else:
            script = result_str

        # If video URL exists, download and upload to S3
        if video_url:
            try:
                import requests
                video_response = requests.get(video_url, timeout=60)
                video_response.raise_for_status()
                
                # Upload to S3
                video_s3_key = await self.storage_service.upload_file(
                    file_content=video_response.content,
                    tenant_id=self.tenant_id,
                    conversation_id=str(self.conversation_id),
                    artifact_type="video",
                    filename=f"ugc_video_{self.conversation_id}.mp4",
                    content_type="video/mp4"
                )
                
                # Create artifact records
                script_artifact = Artifact(
                    conversation_id=self.conversation_id,
                    artifact_type=ArtifactType.SCRIPT,
                    s3_key="",  # Script is stored in metadata
                    s3_url=None,
                    metadata={
                        "script_text": script,
                        "product_name": product_name,
                        "tone": tone,
                        "platform": platform,
                        "ugc_type": ugc_type.value
                    }
                )
                self.db_session.add(script_artifact)

                video_artifact = Artifact(
                    conversation_id=self.conversation_id,
                    artifact_type=ArtifactType.VIDEO,
                    s3_key=video_s3_key,
                    s3_url=self.storage_service.generate_presigned_url(video_s3_key),
                    metadata={
                        "original_url": video_url,
                        "ugc_type": ugc_type.value,
                        "generated_from": "veo_3.1"
                    }
                )
                self.db_session.add(video_artifact)

                await self.db_session.commit()
                logger.info(f"Video uploaded to S3: {video_s3_key}")
                
                return script, self.storage_service.generate_presigned_url(video_s3_key)
            except Exception as e:
                logger.error(f"Error downloading/uploading video: {e}")
                # Still return script even if video upload fails
                return script, None

        return script, None

    async def chat_with_agent(self, message: str) -> str:
        """Handle general chat without image generation."""
        agent = create_chat_agent()
        
        task = Task(
            description=f"""Respond to the user's message: "{message}"
        
Be helpful and informative. If they ask what you can do, explain your UGC generation capabilities.""",
            expected_output="A helpful response to the user's message",
            agent=agent,
            human_input=False
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
            max_iter=3,
            full_output=False
        )
        
        result = crew.kickoff()
        return str(result)

    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temp directory: {self.temp_dir}")

