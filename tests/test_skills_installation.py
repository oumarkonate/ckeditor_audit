"""Every skill in `skills/` must be installed for each agent and documented.

The README stated the skills were symlinked into `~/.claude/skills/` while no link existed, and
Gemini CLI was not mentioned at all. These tests derive the expected set from the filesystem, so
a skill added without its links or its documentation fails immediately.

The symlink assertions depend on the machine: they skip when an agent's skills directory does not
exist (a fresh clone, CI) and fail when it exists but is incomplete — the state that matters.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
AGENTS = {
    "claude": Path.home() / ".claude" / "skills",
    "gemini": Path.home() / ".gemini" / "skills",
}


def _skills() -> list[Path]:
    found = sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))
    assert found, "no SKILL.md found under skills/"
    return found


def _name(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    n = re.search(r"^name:\s*(\S+)", m.group(1), re.M)
    return n.group(1) if n else None


def test_frontmatter_name_matches_directory():
    for d in _skills():
        assert _name(d / "SKILL.md") == d.name, f"{d.name}: frontmatter name differs from directory"


@pytest.mark.parametrize("agent", sorted(AGENTS))
def test_every_skill_is_symlinked(agent):
    base = AGENTS[agent]
    if not base.is_dir():
        pytest.skip(f"{base} absent on this machine")
    missing = [d.name for d in _skills()
               if not (base / d.name).is_symlink() or (base / d.name).resolve() != d.resolve()]
    assert not missing, f"not linked (or linked elsewhere) in {base}: {missing}"


@pytest.mark.parametrize("agent", sorted(AGENTS))
def test_no_dangling_ckeditor_links(agent):
    base = AGENTS[agent]
    if not base.is_dir():
        pytest.skip(f"{base} absent on this machine")
    dangling = [p.name for p in base.glob("ckeditor-*") if p.is_symlink() and not p.exists()]
    assert not dangling, f"broken links in {base}: {dangling}"


@pytest.mark.parametrize("doc", ["README.md", "SETUP.md"])
def test_every_skill_is_documented(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    absent = [d.name for d in _skills() if f"/{d.name}" not in text]
    assert not absent, f"{doc} does not mention: {absent}"


@pytest.mark.parametrize("agent", sorted(AGENTS))
def test_setup_gives_the_install_command_for_each_agent(agent):
    text = (ROOT / "SETUP.md").read_text(encoding="utf-8")
    absent = [d.name for d in _skills()
              if not re.search(rf'ln -sfn "\$\(pwd\)/skills/{d.name}"\s+~/\.{agent}/skills/{d.name}', text)]
    assert not absent, f"SETUP.md has no {agent} install command for: {absent}"
