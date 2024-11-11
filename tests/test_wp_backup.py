import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wp_backup import WordPressBackup, ConfigurationError


@pytest.fixture
def backup_instance():
    with patch.dict(
        "os.environ",
        {
            "WP_SITE_URL": "https://example.com",
            "WP_USERNAME": "test_user",
            "WP_APP_PASSWORD": "test_password",
            "BACKUP_DIR": "test_backups",
        },
    ):
        instance = WordPressBackup()
        yield instance

        # Cleanup after all tests
        if instance.backup_dir.exists():
            # Remove all files in the backup directory
            for file in instance.backup_dir.glob("**/*"):
                if file.is_file():
                    file.unlink()
            # Remove all directories (including nested ones)
            for dir in sorted(instance.backup_dir.glob("**/*"), reverse=True):
                if dir.is_dir():
                    dir.rmdir()
            # Remove the main backup directory
            if instance.backup_dir.exists():
                instance.backup_dir.rmdir()


def test_init(backup_instance):
    assert backup_instance.site_url == "https://example.com.wordpress.com"
    assert backup_instance.username == "test_user"
    assert backup_instance.app_password == "test_password"
    assert str(backup_instance.backup_dir) == "test_backups"


@patch("wp_backup.load_dotenv")
def test_missing_config(mock_load_dotenv):
    # Mock load_dotenv to do nothing
    mock_load_dotenv.return_value = None

    with patch.dict("os.environ", clear=True):
        with pytest.raises(
            ConfigurationError, match="Required environment variables are not set"
        ):
            WordPressBackup()


@patch("requests.get")
def test_fetch_all_items(mock_get, backup_instance):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 1, "name": "Test"}]
    mock_response.headers = {"X-WP-Total": "1", "X-WP-TotalPages": "1"}
    mock_get.return_value = mock_response

    items = backup_instance.fetch_all_items("test_endpoint")
    assert len(items) == 1
    assert items[0]["id"] == 1
    assert items[0]["name"] == "Test"


@patch("wp_backup.WordPressBackup.fetch_all_items")
def test_fetch_taxonomies(mock_fetch_all_items, backup_instance):
    mock_fetch_all_items.side_effect = [
        [{"id": 1, "name": "Category 1"}],
        [{"id": 1, "name": "Tag 1"}],
    ]

    backup_instance.fetch_taxonomies()
    assert len(backup_instance.categories) == 1
    assert len(backup_instance.tags) == 1

    # Cleanup
    tax_file = backup_instance.backup_dir / "taxonomies.json"
    if tax_file.exists():
        tax_file.unlink()


@patch("wp_backup.WordPressBackup.fetch_all_items")
def test_fetch_authors(mock_fetch_all_items, backup_instance):
    mock_fetch_all_items.return_value = [{"id": 1, "name": "Author 1"}]

    backup_instance.fetch_authors()
    assert len(backup_instance.authors) == 1

    # Cleanup
    authors_file = backup_instance.backup_dir / "authors.json"
    if authors_file.exists():
        authors_file.unlink()


@patch("wp_backup.WordPressBackup.fetch_all_items")
def test_fetch_media(mock_fetch_all_items, backup_instance):
    mock_fetch_all_items.return_value = [
        {"id": 1, "source_url": "https://example.com/media/1"}
    ]

    backup_instance.fetch_media()
    assert len(backup_instance.media) == 1

    # Cleanup
    media_file = backup_instance.backup_dir / "media.json"
    if media_file.exists():
        media_file.unlink()

    # Also cleanup media directory if it exists
    media_dir = backup_instance.backup_dir / "media"
    if media_dir.exists():
        media_dir.rmdir()


@patch("wp_backup.WordPressBackup.fetch_all_items")
def test_get_all_posts(mock_fetch_all_items, backup_instance):
    mock_fetch_all_items.return_value = [{"id": 1, "title": {"rendered": "Post 1"}}]

    posts = backup_instance.get_all_posts()
    assert len(posts) == 1
    assert posts[0]["title"]["rendered"] == "Post 1"


@patch("requests.get")
def test_save_post(mock_get, backup_instance):
    post = {
        "id": 1,
        "date": "2023-01-01T00:00:00Z",
        "modified": "2023-01-01T00:00:00Z",
        "slug": "test-post",
        "title": {"rendered": "Test Post"},
        "content": {"rendered": "Test content"},
        "excerpt": {"rendered": "Test excerpt"},
        "author": 1,
        "featured_media": 1,
        "status": "publish",
    }
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"Test media content"

    backup_instance.authors = {1: {"name": "Author 1"}}
    backup_instance.media = {1: {"source_url": "https://example.com/media/1"}}

    filepath = backup_instance.save_post(post)
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        content = f.read()
        assert "Test Post" in content
        assert "Test content" in content

    # Cleanup handled by fixture


@patch("wp_backup.WordPressBackup.fetch_taxonomies")
@patch("wp_backup.WordPressBackup.fetch_authors")
@patch("wp_backup.WordPressBackup.fetch_media")
@patch("wp_backup.WordPressBackup.get_all_posts")
@patch("wp_backup.WordPressBackup.save_post")
def test_backup(
    mock_save_post,
    mock_get_all_posts,
    mock_fetch_media,
    mock_fetch_authors,
    mock_fetch_taxonomies,
    backup_instance,
):
    mock_get_all_posts.return_value = [
        {
            "id": 1,
            "title": {"rendered": "Post 1"},
            "date": "2023-01-01T00:00:00Z",
            "modified": "2023-01-01T00:00:00Z",
            "slug": "test-post",
        }
    ]
    mock_save_post.return_value = "test_backups/2023/01/test-post.md"

    backup_instance.backup()

    mock_fetch_taxonomies.assert_called_once()
    mock_fetch_authors.assert_called_once()
    mock_fetch_media.assert_called_once()
    mock_get_all_posts.assert_called_once()
    mock_save_post.assert_called_once()

    # Cleanup handled by fixture
