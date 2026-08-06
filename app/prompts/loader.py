from pathlib import Path


class PromptLoadError(ValueError):
    pass


class PromptLoader:
    """Loads a versioned Agent prompt relative to its manifest directory."""

    def load(self, manifest):
        if not manifest.source_path:
            raise PromptLoadError("Prompt loading requires a manifest source path")
        reference = Path(manifest.system_prompt_ref)
        if reference.is_absolute():
            raise PromptLoadError("prompt.system must be a relative path")

        manifest_dir = Path(manifest.source_path).resolve().parent
        prompt_path = (manifest_dir / reference).resolve()
        if prompt_path != manifest_dir and manifest_dir not in prompt_path.parents:
            raise PromptLoadError("Prompt path must remain inside the Agent directory")
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise PromptLoadError(f"Unable to load Agent prompt: {reference}") from error
        if not content:
            raise PromptLoadError(f"Agent prompt is empty: {reference}")
        return content
