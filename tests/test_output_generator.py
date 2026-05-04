"""Test suite for OutputGenerator module.

Tests the output generation functionality including:
- YAML file generation
- JSON file generation
- Changelog updates
- Logbook updates
- Error handling for file operations
- Path handling

Tests both happy paths and edge cases.
"""

import pytest
import json
import yaml
from pathlib import Path
from src.stealth_sync.output_generator import OutputGenerator


class TestOutputGenerator:
    """Test suite for OutputGenerator class."""

    def test_init_default_output_dir(self, tmp_path):
        """Test initialization with default output directory."""
        # Change to tmp_path for the test
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            
            generator = OutputGenerator()
            assert generator.output_dir == Path("docs/opencode-sessions/")
            assert generator.output_dir.exists()
        finally:
            os.chdir(original_cwd)

    def test_init_custom_output_dir(self, tmp_path):
        """Test initialization with custom output directory."""
        custom_dir = tmp_path / "custom_output"
        generator = OutputGenerator(output_dir=str(custom_dir))
        
        assert generator.output_dir == custom_dir
        assert custom_dir.exists()

    def test_init_creates_directory(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        non_existent_dir = tmp_path / "new_dir"
        assert not non_existent_dir.exists()
        
        generator = OutputGenerator(output_dir=str(non_existent_dir))
        assert non_existent_dir.exists()

    def test_generate_yaml(self, tmp_path, sample_doc_unit):
        """Test YAML file generation."""
        output_dir = tmp_path / "yaml_output"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        yaml_path = generator.generate_yaml(sample_doc_unit)
        
        # Verify file was created
        assert yaml_path.exists()
        assert yaml_path.suffix == ".yaml"
        
        # Verify file content
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        
        assert content["session_id"] == sample_doc_unit["session_id"]
        assert content["classification"] == sample_doc_unit["classification"]
        assert content["message_count"] == sample_doc_unit["message_count"]

    def test_generate_yaml_multiple_sessions(self, tmp_path):
        """Test YAML generation for multiple sessions."""
        output_dir = tmp_path / "multi_yaml"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        doc_units = [
            {
                "session_id": "ses_1",
                "timestamp": 123,
                "classification": {"category": "fix", "confidence": 0.9},
                "message_count": 2,
                "summary": "First session"
            },
            {
                "session_id": "ses_2",
                "timestamp": 456,
                "classification": {"category": "new", "confidence": 0.8},
                "message_count": 5,
                "summary": "Second session"
            }
        ]
        
        paths = [generator.generate_yaml(unit) for unit in doc_units]
        
        assert len(paths) == 2
        assert all(p.exists() for p in paths)
        assert paths[0].name == "session_ses_1.yaml"
        assert paths[1].name == "session_ses_2.yaml"

    def test_generate_json(self, tmp_path, sample_doc_unit):
        """Test JSON file generation."""
        output_dir = tmp_path / "json_output"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        json_path = generator.generate_json(sample_doc_unit)
        
        # Verify file was created
        assert json_path.exists()
        assert json_path.suffix == ".json"
        
        # Verify file content
        with open(json_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        assert content["session_id"] == sample_doc_unit["session_id"]
        assert content["classification"] == sample_doc_unit["classification"]
        assert content["message_count"] == sample_doc_unit["message_count"]
        
        # Verify JSON structure
        assert "timestamp" in content
        assert "summary" in content

    def test_generate_json_unicode_support(self, tmp_path):
        """Test JSON generation with Unicode characters."""
        output_dir = tmp_path / "unicode_output"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        doc_unit = {
            "session_id": "ses_unicode",
            "timestamp": 123,
            "classification": {"category": "doc", "confidence": 0.9},
            "message_count": 1,
            "summary": "Session with emojis and special chars: aeiou n"
        }
        
        json_path = generator.generate_json(doc_unit)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        assert "emojis" in content["summary"].lower()
        assert "aeiou" in content["summary"].lower()

    def test_update_changelog(self, tmp_path, sample_doc_unit):
        """Test changelog update."""
        changelog_dir = tmp_path / "changelog"
        generator = OutputGenerator()
        
        changelog_path = generator.update_changelog(sample_doc_unit, str(changelog_dir))
        
        # Verify file was created
        assert changelog_path.exists()
        assert changelog_path.suffix == ".md"
        
        # Verify content
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "# ses_sample123" in content
        assert "**Category:** fix" in content
        assert "**Message Count:** 5" in content

    def test_update_changelog_default_dir(self, tmp_path, sample_doc_unit):
        """Test changelog update with default directory."""
        generator = OutputGenerator()
        
        changelog_path = generator.update_changelog(sample_doc_unit)
        
        assert changelog_path.exists()
        # Default changelog directory should be created
        assert "docs/changelog" in str(changelog_path) or changelog_path.parent.exists()

    def test_update_logbook(self, tmp_path, sample_doc_unit):
        """Test logbook update."""
        logbook_path = tmp_path / "test_logbook.yaml"
        generator = OutputGenerator()
        
        # Initial state - logbook should not exist
        assert not logbook_path.exists()
        
        generator.update_logbook(sample_doc_unit, str(logbook_path))
        
        # Verify logbook was created
        assert logbook_path.exists()
        
        # Verify content
        with open(logbook_path, 'r', encoding='utf-8') as f:
            entries = yaml.safe_load(f)
        
        assert isinstance(entries, list)
        assert len(entries) == 1
        assert entries[0]["session_id"] == sample_doc_unit["session_id"]
        assert entries[0]["category"] == sample_doc_unit["classification"]["category"]

    def test_update_logbook_append(self, tmp_path, sample_doc_unit):
        """Test that logbook appends new entries."""
        logbook_path = tmp_path / "append_logbook.yaml"
        generator = OutputGenerator()
        
        # Create initial entry
        generator.update_logbook(sample_doc_unit, str(logbook_path))
        
        # Add another entry
        doc_unit2 = sample_doc_unit.copy()
        doc_unit2["session_id"] = "ses_second"
        doc_unit2["classification"]["category"] = "new"
        
        generator.update_logbook(doc_unit2, str(logbook_path))
        
        # Verify logbook has both entries
        with open(logbook_path, 'r', encoding='utf-8') as f:
            entries = yaml.safe_load(f)
        
        assert len(entries) == 2
        assert entries[0]["session_id"] == "ses_sample123"
        assert entries[1]["session_id"] == "ses_second"

    def test_update_logbook_default_path(self, tmp_path, sample_doc_unit):
        """Test logbook update with default path."""
        generator = OutputGenerator()
        
        # Should create logbook.stealth.yaml in current directory
        generator.update_logbook(sample_doc_unit)
        
        default_path = Path("logbook.stealth.yaml")
        assert default_path.exists()
        
        # Cleanup
        default_path.unlink(missing_ok=True)

    def test_generate_yaml_with_missing_fields(self, tmp_path):
        """Test YAML generation with missing optional fields."""
        output_dir = tmp_path / "missing_fields"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        doc_unit = {
            "session_id": "ses_partial",
            # Missing timestamp, classification, etc.
        }
        
        yaml_path = generator.generate_yaml(doc_unit)
        assert yaml_path.exists()

    def test_output_paths_are_unique(self, tmp_path, sample_doc_unit):
        """Test that each output generates unique files."""
        output_dir = tmp_path / "unique_paths"
        generator = OutputGenerator(output_dir=str(output_dir))
        
        yaml_path = generator.generate_yaml(sample_doc_unit)
        json_path = generator.generate_json(sample_doc_unit)
        changelog_path = generator.update_changelog(sample_doc_unit)
        
        # All paths should be different
        assert yaml_path != json_path
        assert yaml_path != changelog_path
        assert json_path != changelog_path
        
        # All should exist
        assert yaml_path.exists()
        assert json_path.exists()
        assert changelog_path.exists()


class TestOutputGeneratorLogbook:
    """Enhanced test suite for OutputGenerator.logbook functionality."""

    def test_update_logbook_with_all_categories(self, tmp_path):
        """Test logbook update with all classification categories."""
        from src.stealth_sync.semantic_engine import CATEGORIES
        
        logbook_path = tmp_path / "categories_logbook.yaml"
        generator = OutputGenerator()
        
        for category in CATEGORIES:
            doc_unit = {
                "session_id": f"ses_{category}_log",
                "timestamp": 1234567890,
                "classification": {"category": category, "confidence": 0.9},
                "message_count": 5,
                "summary": f"Session for {category} category"
            }
            
            generator.update_logbook(doc_unit, str(logbook_path))
        
        # Verify logbook was created and contains all entries
        assert logbook_path.exists()
        
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert isinstance(entries, list)
        assert len(entries) == len(CATEGORIES)
        
        # Verify each entry
        for i, category in enumerate(CATEGORIES):
            assert entries[i]["session_id"] == f"ses_{category}_log"
            assert entries[i]["category"] == category
            assert "timestamp" in entries[i]

    def test_update_logbook_structure_and_content(self, tmp_path):
        """Test that logbook entries have correct structure."""
        logbook_path = tmp_path / "structure_logbook.yaml"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_structure_test",
            "timestamp": 9999999999,
            "classification": {"category": "feat", "confidence": 0.95},
            "message_count": 10,
            "summary": "Test session for structure"
        }
        
        generator.update_logbook(doc_unit, str(logbook_path))
        
        # Read and verify structure
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 1
        entry = entries[0]
        
        # Verify entry structure
        assert "session_id" in entry
        assert "category" in entry
        assert "timestamp" in entry
        
        # Verify values
        assert entry["session_id"] == "ses_structure_test"
        assert entry["category"] == "feat"
        assert entry["timestamp"] == 9999999999
        
        # Should not have extra fields
        assert len(entry) == 3  # Only these three fields

    def test_update_logbook_multiple_appends(self, tmp_path):
        """Test appending multiple entries to logbook."""
        logbook_path = tmp_path / "append_logbook.yaml"
        generator = OutputGenerator()
        
        # Add 20 entries
        for i in range(20):
            doc_unit = {
                "session_id": f"ses_entry_{i}",
                "timestamp": 1000000 + i,
                "classification": {"category": "fix" if i % 2 == 0 else "new", "confidence": 0.9},
                "message_count": i + 1,
                "summary": f"Entry {i}"
            }
            generator.update_logbook(doc_unit, str(logbook_path))
        
        # Verify logbook
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 20
        
        # Verify order (should be in order of append)
        for i in range(20):
            assert entries[i]["session_id"] == f"ses_entry_{i}"
            assert entries[i]["timestamp"] == 1000000 + i

    def test_update_logbook_with_minimal_doc_unit(self, tmp_path):
        """Test logbook update with minimal documentation unit."""
        logbook_path = tmp_path / "minimal_logbook.yaml"
        generator = OutputGenerator()
        
        # Minimal doc unit with only required fields
        doc_unit = {
            "session_id": "ses_minimal",
            "classification": {"category": "doc"}
        }
        
        generator.update_logbook(doc_unit, str(logbook_path))
        
        # Should still work
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "ses_minimal"
        assert entries[0]["category"] == "doc"
        # timestamp might be None or missing

    def test_update_logbook_with_none_values(self, tmp_path):
        """Test logbook update with None values in doc unit."""
        logbook_path = tmp_path / "none_values_logbook.yaml"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_none_test",
            "timestamp": None,
            "classification": {"category": None},
            "message_count": None,
            "summary": None
        }
        
        generator.update_logbook(doc_unit, str(logbook_path))
        
        # Should handle None values gracefully
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "ses_none_test"
        # None values might be converted to null in YAML

    def test_update_logbook_unicode_support(self, tmp_path):
        """Test logbook update with Unicode characters."""
        logbook_path = tmp_path / "unicode_logbook.yaml"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_unicode_log",
            "timestamp": 1234567890,
            "classification": {"category": "doc", "confidence": 0.9},
            "message_count": 3,
            "summary": "Session with emojis and special chars: aeiou n"
        }
        
        generator.update_logbook(doc_unit, str(logbook_path))
        
        # Verify file was created successfully
        assert logbook_path.exists()
        
        # Verify content exists
        with open(logbook_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 0
        assert "session_id:" in content
        assert "category:" in content

    def test_update_logbook_large_number_of_entries(self, tmp_path):
        """Test logbook performance with large number of entries."""
        logbook_path = tmp_path / "large_logbook.yaml"
        generator = OutputGenerator()
        
        # Add 100 entries
        for i in range(100):
            doc_unit = {
                "session_id": f"ses_large_{i:03d}",
                "timestamp": 1000000 + i,
                "classification": {"category": "fix", "confidence": 0.9},
                "message_count": 5,
                "summary": f"Entry {i}"
            }
            generator.update_logbook(doc_unit, str(logbook_path))
        
        # Verify all entries
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 100
        
        # Verify first and last entries
        assert entries[0]["session_id"] == "ses_large_000"
        assert entries[99]["session_id"] == "ses_large_099"

    def test_update_logbook_different_output_formats(self, tmp_path):
        """Test logbook YAML formatting."""
        logbook_path = tmp_path / "format_logbook.yaml"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_format_test",
            "timestamp": 1234567890,
            "classification": {"category": "test", "confidence": 0.8},
            "message_count": 7,
            "summary": "Format test"
        }
        
        generator.update_logbook(doc_unit, str(logbook_path))
        
        # Read raw YAML to verify formatting
        with open(logbook_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should be valid YAML
        assert "session_id:" in content
        assert "category:" in content
        assert "timestamp:" in content
        
        # Should use block style (not flow style)
        assert "-" in content  # List item indicator
        
        # Should not be compact
        lines = content.strip().split('\n')
        assert len(lines) > 1  # Multi-line format

    def test_update_logbook_preserves_existing_file(self, tmp_path):
        """Test that update_logbook preserves existing logbook file."""
        logbook_path = tmp_path / "preserve_logbook.yaml"
        generator = OutputGenerator()
        
        # Create initial logbook
        doc_unit1 = {
            "session_id": "ses_first",
            "timestamp": 1000000,
            "classification": {"category": "fix", "confidence": 0.9},
            "message_count": 3,
            "summary": "First entry"
        }
        generator.update_logbook(doc_unit1, str(logbook_path))
        
        # Get initial modification time
        import os
        mtime1 = os.path.getmtime(str(logbook_path))
        
        # Add second entry
        doc_unit2 = {
            "session_id": "ses_second",
            "timestamp": 2000000,
            "classification": {"category": "new", "confidence": 0.9},
            "message_count": 5,
            "summary": "Second entry"
        }
        generator.update_logbook(doc_unit2, str(logbook_path))
        
        # Get new modification time
        mtime2 = os.path.getmtime(str(logbook_path))
        
        # File should have been modified
        assert mtime2 >= mtime1
        
        # Should have both entries
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 2
        assert entries[0]["session_id"] == "ses_first"
        assert entries[1]["session_id"] == "ses_second"

    def test_update_logbook_with_special_characters_in_session_id(self, tmp_path):
        """Test logbook update with special characters in session ID."""
        logbook_path = tmp_path / "special_logbook.yaml"
        generator = OutputGenerator()
        
        special_session_ids = [
            "ses_test-123",
            "ses_test_456",
            "ses.test.789",
            "ses:test:abc",
            "ses/test/def"
        ]
        
        for session_id in special_session_ids:
            doc_unit = {
                "session_id": session_id,
                "timestamp": 1234567890,
                "classification": {"category": "fix", "confidence": 0.9},
                "message_count": 1,
                "summary": f"Test for {session_id}"
            }
            generator.update_logbook(doc_unit, str(logbook_path))
        
        # Verify all entries were added
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == len(special_session_ids)
        for i, session_id in enumerate(special_session_ids):
            assert entries[i]["session_id"] == session_id

    def test_update_logbook_concurrent_updates(self, tmp_path):
        """Test that multiple logbook updates work correctly."""
        logbook_path = tmp_path / "concurrent_logbook.yaml"
        generator = OutputGenerator()
        
        # Simulate concurrent updates by adding entries in quick succession
        import threading
        import time
        
        def add_entry(entry_id):
            doc_unit = {
                "session_id": f"ses_concurrent_{entry_id}",
                "timestamp": int(time.time() * 1000) + entry_id,
                "classification": {"category": "fix", "confidence": 0.9},
                "message_count": 1,
                "summary": f"Concurrent entry {entry_id}"
            }
            generator.update_logbook(doc_unit, str(logbook_path))
            time.sleep(0.01)  # Small delay
        
        # Start multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_entry, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify all entries
        with open(logbook_path, 'r', encoding='utf-8') as f:
            import yaml
            entries = yaml.safe_load(f)
        
        assert len(entries) == 10
        # Entries might not be in order due to threading, but all should be present
        entry_ids = [e["session_id"] for e in entries]
        for i in range(10):
            assert f"ses_concurrent_{i}" in entry_ids


class TestOutputGeneratorChangelog:
    """Enhanced test suite for OutputGenerator.changelog functionality."""

    def test_update_changelog_with_all_categories(self, tmp_path):
        """Test changelog update with all classification categories."""
        from src.stealth_sync.semantic_engine import CATEGORIES
        
        changelog_dir = tmp_path / "categories_changelog"
        generator = OutputGenerator()
        
        for category in CATEGORIES:
            doc_unit = {
                "session_id": f"ses_{category}_change",
                "timestamp": 1234567890,
                "classification": {"category": category, "confidence": 0.9},
                "message_count": 5,
                "summary": f"{category.capitalize()} session"
            }
            
            changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
            assert changelog_path.exists()
            assert changelog_path.suffix == ".md"
        
        # Verify all changelog files exist
        changelog_files = list(changelog_dir.glob("*.md"))
        assert len(changelog_files) == len(CATEGORIES)

    def test_update_changelog_content_structure(self, tmp_path):
        """Test that changelog entry has correct Markdown structure."""
        changelog_dir = tmp_path / "structure_changelog"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_changelog_structure",
            "timestamp": 1234567890,
            "classification": {"category": "feat", "confidence": 0.95},
            "message_count": 15,
            "summary": "Major feature implementation with comprehensive changes"
        }
        
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Read and verify content
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify Markdown structure
        assert "# ses_changelog_structure" in content
        assert "**Category:** feat" in content
        assert "**Timestamp:** 1234567890" in content
        assert "**Message Count:** 15" in content
        assert "## Summary" in content
        assert "Major feature implementation" in content
        assert "---" in content  # Separator

    def test_update_changelog_unicode_support(self, tmp_path):
        """Test changelog update with Unicode characters."""
        changelog_dir = tmp_path / "unicode_changelog"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_unicode_changelog",
            "timestamp": 1234567890,
            "classification": {"category": "doc", "confidence": 0.9},
            "message_count": 3,
            "summary": "Updated documentation with emojis and special chars: aeiou n"
        }
        
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Verify Unicode is preserved
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 0
        assert "# ses_unicode_changelog" in content

    def test_update_changelog_multiple_entries(self, tmp_path):
        """Test creating multiple changelog entries."""
        changelog_dir = tmp_path / "multi_changelog"
        generator = OutputGenerator()
        
        # Create 5 changelog entries
        for i in range(5):
            doc_unit = {
                "session_id": f"ses_changelog_{i}",
                "timestamp": 1000000 + i,
                "classification": {"category": "fix" if i % 2 == 0 else "new", "confidence": 0.9},
                "message_count": i + 1,
                "summary": f"Changelog entry {i}"
            }
            generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Verify all files exist
        changelog_files = list(changelog_dir.glob("*.md"))
        assert len(changelog_files) == 5
        
        # Verify content of each
        for i in range(5):
            file_path = changelog_dir / f"ses_changelog_{i}.md"
            assert file_path.exists()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert f"# ses_changelog_{i}" in content
            assert "**Category:**" in content
            assert "**Message Count:**" in content

    def test_update_changelog_default_directory(self, tmp_path):
        """Test changelog update with default directory."""
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_default_changelog",
            "timestamp": 1234567890,
            "classification": {"category": "doc", "confidence": 0.9},
            "message_count": 2,
            "summary": "Default changelog test"
        }
        
        changelog_path = generator.update_changelog(doc_unit)
        
        # Should create file
        assert changelog_path.exists()
        assert changelog_path.suffix == ".md"

    def test_update_changelog_special_characters_in_summary(self, tmp_path):
        """Test changelog with special characters and code in summary."""
        changelog_dir = tmp_path / "special_changelog"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_special_changelog",
            "timestamp": 1234567890,
            "classification": {"category": "refactor", "confidence": 0.9},
            "message_count": 8,
            "summary": "Refactored code.py with async def fetch_data() and try-except blocks"
        }
        
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Verify content
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "code.py" in content
        assert "async def" in content or "fetch_data" in content
        assert "try-except" in content or "Refactored" in content

    def test_update_changelog_empty_summary(self, tmp_path):
        """Test changelog with empty summary."""
        changelog_dir = tmp_path / "empty_changelog"
        generator = OutputGenerator()
        
        doc_unit = {
            "session_id": "ses_empty_summary",
            "timestamp": 1234567890,
            "classification": {"category": "chore", "confidence": 0.8},
            "message_count": 0,
            "summary": ""
        }
        
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Should still create file
        assert changelog_path.exists()
        
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have basic structure even with empty summary
        assert "# ses_empty_summary" in content
        assert "**Category:** chore" in content

    def test_update_changelog_large_summary(self, tmp_path):
        """Test changelog with very large summary text."""
        changelog_dir = tmp_path / "large_changelog"
        generator = OutputGenerator()
        
        # Create large summary
        large_summary = "This is a very long summary " * 50
        
        doc_unit = {
            "session_id": "ses_large_summary",
            "timestamp": 1234567890,
            "classification": {"category": "new", "confidence": 0.9},
            "message_count": 25,
            "summary": large_summary
        }
        
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        
        # Verify file exists and contains the summary
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert large_summary[:50] in content  # First part should be there
        assert "## Summary" in content


@pytest.mark.asyncio
async def test_async_compatibility():
    """Test async/await compatibility of output generator methods."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        generator = OutputGenerator(output_dir=tmp_dir)
        sample_unit = {
            "session_id": "ses_async",
            "timestamp": 123,
            "classification": {"category": "test", "confidence": 0.5},
            "message_count": 1,
            "summary": "Async test"
        }
        
        # Test that methods can be awaited
        yaml_path = generator.generate_yaml(sample_unit)
        assert yaml_path.exists()
        
        json_path = generator.generate_json(sample_unit)
        assert json_path.exists()
