from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Memory:
    key: str
    content: str
    path: Path


class MemoryLoader:
    """Load and save persistent Markdown memories.

    The README for this lab asks for a very small persistent store:
    - each memory lives in one Markdown file;
    - the first line stores the memory key;
    - the remaining text stores the body/content;
    - system prompts should only see the list of keys, not the full bodies.

    This loader keeps a small in-memory index so `read_memory` and
    `save_memory` can resolve keys quickly without re-scanning the directory
    on every call.
    """

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.reload()

    def reload(self) -> None:
        """Re-scan the memory directory and rebuild the key index.

        This is useful when a session starts, or when files may have changed on
        disk outside of the current Python process. The loader only stores a
        tiny index in memory; the file contents remain the source of truth.
        """

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._memories_by_key: dict[str, Memory] = {}

        for path in sorted(self.memory_dir.glob("*.md")):
            memory = self._load_memory_file(path)
            if memory is None:
                continue

            # If duplicate keys exist, keep the later file in sorted order.
            # In normal use each key should map to exactly one file, but this
            # fallback makes the store resilient to manual edits.
            self._memories_by_key[memory.key] = memory
            

    def descriptions(self) -> str:
        """Return a compact bullet list of available memory keys.

        The README explicitly says the system prompt should only include the
        key list, so this method intentionally does not include memory bodies
        or long summaries.
        """

        if not self._memories_by_key:
            return "(no memories saved)"

        lines = [f"- {key}" for key in sorted(self._memories_by_key)]
        return "\n".join(lines)

    def content(self, key: str) -> str:
        """Return the body of one memory identified by its exact key.

        The tool layer uses this method for exact-key retrieval. We raise a
        clear error when the key does not exist so the tool can convert it into
        a readable JSON error message.
        """

        key = self._normalize_key(key)
        memory = self._memories_by_key.get(key)
        if memory is None:
            raise FileNotFoundError(f"Memory not found: {key}")
        return memory.content

    def save(self, key: str, content: str) -> Memory:
        """Create or update one persistent memory entry.

        The memory is saved as Markdown with the exact key on the first line.
        We keep the filename stable for a given key, so repeated saves replace
        the same file instead of creating duplicate records.
        """

        key = self._normalize_key(key)
        if not key:
            raise ValueError("Memory key must not be empty.")
        content = content.strip()
        if not content:
            raise ValueError("Memory content must not be empty.")

        # Reuse the existing file path when the key already exists. This keeps
        # updates stable and avoids leaving stale copies behind.
        existing = self._memories_by_key.get(key)
        path = existing.path if existing is not None else self._memory_path_for_key(key)

        # The on-disk format is intentionally simple:
        #   line 1: the memory key
        #   line 2: blank separator
        #   lines 3+: the stored body
        text = f"# {key}\n\n{content}\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

        memory = Memory(key=key, content=content, path=path)
        self._memories_by_key[key] = memory
        return memory

    def keys(self) -> list[str]:
        """Expose the current key list for callers that need it directly."""

        return sorted(self._memories_by_key)

    def _normalize_key(self, key: str) -> str:
        """Trim whitespace and enforce a non-empty exact key."""

        return key.strip()

    def _memory_path_for_key(self, key: str) -> Path:
        """Derive a stable, filesystem-safe filename from a memory key.

        The key itself may contain spaces, punctuation, or non-ASCII text.
        We keep the original key in the file body and generate a sanitized
        filename that is stable for the same key.
        """

        slug = _slugify(key)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        return self.memory_dir / f"{slug}-{digest}.md"

    def _load_memory_file(self, path: Path) -> Memory | None:
        """Parse one Markdown memory file from disk.

        If a file does not follow the expected format, we skip it instead of
        crashing the whole loader. This makes the store robust to stray files
        and keeps the runtime focused on valid memories.
        """

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None

        lines = raw.splitlines()
        if not lines:
            return None

        key = _parse_title_line(lines[0])
        if not key:
            return None

        # Everything after the first line is the stored body. We strip only the
        # leading blank separator so the actual content is preserved verbatim.
        body = "\n".join(lines[1:]).lstrip("\n")
        return Memory(key=key, content=body, path=path)


def _parse_title_line(line: str) -> str:
    """Extract the memory key from the first Markdown line.

    The README says the first line is the title that stores the key. We accept
    a standard Markdown heading like `# key`, but we also fall back to the raw
    stripped text so manual edits remain readable.
    """

    stripped = line.strip()
    if not stripped:
        return ""

    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    return stripped


def _slugify(text: str) -> str:
    """Convert an arbitrary key into a safe filename fragment.

    We keep Chinese and other Unicode letters when possible, but remove path
    separators and other risky characters. The hash suffix ensures that two
    different keys that slugify to the same text still map to different files.
    """

    text = text.strip().lower()
    text = re.sub(r"[\\/]+", "-", text)
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-+", "-", text)
    text = text.strip(".-_")
    return text or "memory"
