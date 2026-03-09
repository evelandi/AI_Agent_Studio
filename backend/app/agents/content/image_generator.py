"""
Wrapper de Diffusers (HuggingFace) para generación local de imágenes.
Modelo configurable via IMAGE_MODEL_ID en .env

Implementación completa: Fase 6
"""
from pathlib import Path
from app.config import settings


class ImageGenerator:
    """
    Genera imágenes a partir de un prompt de texto usando Stable Diffusion local.
    El modelo se carga una sola vez y se reutiliza (singleton pattern).
    """

    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        if cls._pipeline is None:
            # Import diferido para no requerir GPU en desarrollo
            from diffusers import StableDiffusionPipeline
            import torch
            cls._pipeline = StableDiffusionPipeline.from_pretrained(
                settings.image_model_id,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
            if torch.cuda.is_available():
                cls._pipeline = cls._pipeline.to("cuda")
        return cls._pipeline

    @classmethod
    def generate(cls, prompt: str, filename: str) -> str:
        """
        Genera una imagen y la guarda en IMAGE_OUTPUT_DIR.
        Retorna la ruta absoluta del archivo generado.
        """
        # TODO: Fase 6 — implementar generación completa
        raise NotImplementedError("ImageGenerator: implementar en Fase 6")
