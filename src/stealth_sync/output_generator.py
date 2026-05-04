"""Output generators for documentation units.

This module handles generating structured documentation from analyzed
OpenCode sessions. It supports YAML, JSON, Markdown changelog,
and central logbook formats.

The documentation units follow a consistent schema:
  - session_id: OpenCode session ID
  - timestamp: Unix timestamp of generation
  - classification: Dict with category and confidence
  - message_count: Number of messages in session
  - summary: Text summary of session content
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any
import structlog

# Initialize module logger
logger = structlog.get_logger(__name__)


class OutputGenerator:
    """Generates structured documentation from session analysis.
    
    This class creates various output formats from the documentation
    units produced by the SemanticAnalyzer. Outputs include:
      - YAML files per session (for human-readable docs)
      - JSON files per session (for programmatic processing)
      - Markdown changelog entries (for tracking changes)
      - Central logbook YAML (for quick reference)
    
    Attributes:
        output_dir: Path to directory for session documentation
    """
    
    def __init__(self, output_dir: str = "docs/opencode-sessions/"):
        """Initialize the output generator.
        
        Args:
            output_dir: Directory where documentation will be saved
                        (created if it doesn't exist)
        """
        self.output_dir = Path(output_dir)
        # Create output directory and parents if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("output_generator_ready", output_dir=str(self.output_dir))
    
    def generate_yaml(self, doc_unit: Dict[str, Any]) -> Path:
        """Generate a YAML documentation file for a session.
        
        Creates a YAML file named session_<session_id>.yaml in the
        output directory. YAML is used for human-readable documentation.
        
        Args:
            doc_unit: Documentation unit dictionary from SemanticAnalyzer
            
        Returns:
            Path to the created YAML file
        """
        session_id = doc_unit.get("session_id", "unknown")
        # Build filename from session ID
        filepath = self.output_dir / f"session_{session_id}.yaml"
        
        # Write YAML with Unicode support and readable format
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(
                doc_unit,
                f,
                default_flow_style=False,  # Block style for readability
                allow_unicode=True,         # Support non-ASCII characters
                sort_keys=False,             # Preserve key order
            )
        
        logger.info("yaml_doc_generated", path=str(filepath))
        return filepath
    
    def generate_json(self, doc_unit: Dict[str, Any]) -> Path:
        """Generate a JSON documentation file for a session.
        
        Creates a JSON file named session_<session_id>.json in the
        output directory. JSON is used for programmatic processing.
        
        Args:
            doc_unit: Documentation unit dictionary from SemanticAnalyzer
            
        Returns:
            Path to the created JSON file
        """
        session_id = doc_unit.get("session_id", "unknown")
        # Build filename from session ID
        filepath = self.output_dir / f"session_{session_id}.json"
        
        # Write JSON with indentation and Unicode support
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                doc_unit,
                f,
                indent=2,           # Pretty print with 2-space indent
                ensure_ascii=False,  # Support non-ASCII characters
            )
        
        logger.info("json_doc_generated", path=str(filepath))
        return filepath
    
    def update_changelog(
        self, doc_unit: Dict[str, Any], changelog_dir: str = "docs/changelog/"
    ) -> Path:
        """Update changelog with a new entry for this session.
        
        Creates a Markdown file in the changelog directory with
        session details. This provides a chronological record of changes.
        
        Args:
            doc_unit: Documentation unit dictionary
            changelog_dir: Directory for changelog entries
            
        Returns:
            Path to the created changelog file
        """
        # Ensure changelog directory exists
        changelog_path = Path(changelog_dir)
        changelog_path.mkdir(parents=True, exist_ok=True)
        
        # Build filename from session ID
        entry_file = changelog_path / f"{doc_unit.get('session_id', 'unknown')}.md"
        
        # Generate Markdown content
        content = self._build_changelog_entry(doc_unit)
        
        # Write Markdown file
        with open(entry_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info("changelog_updated", path=str(entry_file))
        return entry_file
    
    def _build_changelog_entry(self, doc_unit: Dict[str, Any]) -> str:
        """Build a Markdown changelog entry.
        
        Creates a formatted Markdown string with session metadata,
        classification, and summary.
        
        Args:
            doc_unit: Documentation unit dictionary
            
        Returns:
            Markdown formatted string
        """
        classification = doc_unit.get("classification", {})
        
        # Build Markdown content with headers and bullet points
        return f"""# {doc_unit.get('session_id', 'Unknown')}

**Category:** {classification.get('category', 'unknown')}  
**Timestamp:** {doc_unit.get('timestamp', 'N/A')}  
**Message Count:** {doc_unit.get('message_count', 0)}  

## Summary
{doc_unit.get('summary', 'No summary available')}

---
"""
    
    def update_logbook(
        self, doc_unit: Dict[str, Any], logbook_path: str = "logbook.stealth.yaml"
    ) -> None:
        """Update the central logbook with a session reference.
        
        Appends a brief entry to the central logbook YAML file.
        This provides a quick reference to all documented sessions.
        
        Args:
            doc_unit: Documentation unit dictionary
            logbook_path: Path to the logbook YAML file
        """
        logbook = Path(logbook_path)
        
        # Create a brief entry with essential fields only
        entry = {
            "session_id": doc_unit.get("session_id"),
            "category": doc_unit.get("classification", {}).get("category"),
            "timestamp": doc_unit.get("timestamp"),
        }
        
        # Append entry to logbook in YAML format
        with open(logbook, "a", encoding="utf-8") as f:
            yaml.dump(
                [entry],
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        
        logger.info("logbook_updated", path=str(logbook))
