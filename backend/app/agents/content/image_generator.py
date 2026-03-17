"""
Wrapper de Diffusers (HuggingFace) para generacion local de imagenes.
Modelo configurable via IMAGE_MODEL_ID en .env

Modo degradado: si torch/diffusers no estan disponibles (entorno sin GPU),
`generate()` retorna None en lugar de lanzar excepcion — el agente
continua sin imagen.
"""
import structlog
from pathlib import Path
from datetime import datetime, timezone

from app.config import settings

log = structlog.get_logger()


class ImageGenerator:
    """
    Genera imagenes a partir de un prompt de texto usando Stable Diffusion local.
    El modelo se carga una sola vez y se reutiliza (singleton pattern).

    Modo degradado: si no hay GPU o torch/diffusers no estan instalados,
    todas las llamadas a generate() retornan None sin lanzar excepcion.
    """

    _pipeline = None
    _available: bool | None = None  # None = no verificado aun

    @classmethod
    def is_available(cls) -> bool:
        """Verifica si torch y diffusers estan disponibles (se cachea)."""
        if cls._available is not None:
            return cls._available
        try:
            import torch
            import diffusers  # noqa: F401
            cls._available = True
        except ImportError:
            cls._available = False
            log.warning("image_generator.unavailable", reason="torch/diffusers not installed")
        return cls._available

    @classmethod
    def get_pipeline(cls):
        """Carga el pipeline de Stable Diffusion (solo si hay GPU disponible)."""
        if not cls.is_available():
            return None
        if cls._pipeline is not None:
            return cls._pipeline

        try:
            import torch
            from diffusers import StableDiffusionPipeline

            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            pipeline = StableDiffusionPipeline.from_pretrained(
                settings.image_model_id,
                torch_dtype=dtype,
            )
            if torch.cuda.is_available():
                pipeline = pipeline.to("cuda")
            cls._pipeline = pipeline
            log.info("image_generator.pipeline_loaded", model=settings.image_model_id)
        except Exception as exc:
            log.error("image_generator.pipeline_error", error=str(exc))
            cls._available = False
            return None

        return cls._pipeline

    @classmethod
    def generate(cls, prompt: str, filename: str | None = None) -> str | None:
        """
        Genera una imagen y la guarda en IMAGE_OUTPUT_DIR.

        Args:
            prompt: Descripcion en ingles del contenido visual deseado.
            filename: Nombre del archivo (sin extension). Auto-generado si None.

        Returns:
            Ruta absoluta del archivo generado, o None si no hay GPU/diffusers.
        """
        pipeline = cls.get_pipeline()
        if pipeline is None:
            log.info("image_generator.skipped", reason="no GPU pipeline")
            return None

        try:
            output_dir = Path(settings.image_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            if not filename:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = f"content_{ts}"

            output_path = output_dir / f"{filename}.png"

            image = pipeline(prompt, num_inference_steps=30, guidance_scale=7.5).images[0]
            image.save(str(output_path))

            log.info("image_generator.success", path=str(output_path))
            return str(output_path)

        except Exception as exc:
            log.error("image_generator.generate_error", error=str(exc))
            return None


image_generator = ImageGenerator()
