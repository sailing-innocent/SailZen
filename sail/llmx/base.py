from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class GenerationConfig:
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95


@dataclass
class ImageGenerationConfig(GenerationConfig):
    width: int = 1024
    height: int = 1024
    num_images: int = 1
    seed: Optional[int] = None
    reference_image: Optional[bytes] = None
    reference_media: Optional[List[str]] = None


@dataclass
class VideoGenerationConfig(GenerationConfig):
    duration: int = 6
    fps: int = 24
    resolution: str = "1080p"
    first_frame: Optional[bytes] = None
    last_frame: Optional[bytes] = None
    control_video_path: Optional[str] = None
    enable_audio: bool = True
    reference_images: Optional[List[str]] = None


@dataclass
class LLMResponse:
    text: str
    usage: Dict[str, int]
    model: str
    finish_reason: Optional[str] = None
    cost_usd: float = 0.0


@dataclass
class ImageResponse:
    image_bytes: bytes
    mime_type: str
    usage: Dict[str, int]
    model: str
    cost_usd: float = 0.0


@dataclass
class VideoResponse:
    video_bytes: bytes
    duration: float
    resolution: str
    usage: Dict[str, int]
    model: str
    cost_usd: float = 0.0


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
    ) -> Any:
        """Generate structured output using JSON schema enforcement.

        Args:
            prompt: The input prompt
            response_schema: JSON schema defining the expected output structure
            system_prompt: Optional system prompt
            config: Optional generation configuration
            media_path: Optional path to image or video file

        Returns:
            Parsed JSON matching the schema
        """
        pass

    @abstractmethod
    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        pass

    def analyze_images(
        self,
        image_paths: list[str],
        prompt: str,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        return self.analyze_image(image_paths[0], prompt, config)

    @abstractmethod
    def analyze_video(
        self, video_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        pass


class BaseImageProvider(ABC):
    @abstractmethod
    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        pass

    @abstractmethod
    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        pass


class BaseVideoProvider(ABC):
    @abstractmethod
    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        config: Optional[VideoGenerationConfig] = None,
    ) -> VideoResponse:
        pass

    @abstractmethod
    def get_video_status(self, task_id: str) -> Dict[str, Any]:
        pass

    @property
    def embeds_images_in_prompt(self) -> bool:
        """Whether this provider requires image reference tokens in the prompt text.

        - Kling: True — images are referenced via <<<image_N>>> tokens in the prompt.
        - Veo: False — images are passed as separate API parameters, not in the prompt.

        Downstream agents use this to decide whether to inject image tokens into
        the distillation prompt or describe references purely in text.
        """
        return False

    def format_image_reference(self, index: int, label: str) -> str:
        """Return the prompt-visible token/text for referencing an image at `index`.

        Args:
            index: 1-based image index in the provider's image list.
            label: Human-readable description of what this image is.

        Returns:
            A string to embed in the prompt. For providers that embed images in
            prompt (e.g. Kling), returns a token like "<<<image_1>>>".
            For providers that don't (e.g. Veo), returns an empty string.
        """
        return ""

    @property
    def prompt_length_limit(self) -> int:
        """Max prompt length in characters. 0 means no limit."""
        return 0