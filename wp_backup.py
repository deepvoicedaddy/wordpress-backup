import os
import json
import requests
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import frontmatter
from urllib.parse import urlparse, urlencode
import logging
import sys
from base64 import b64encode

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there's an issue with the configuration"""

    pass


class WordPressBackup:
    def __init__(self):
        # Load environment variables
        load_dotenv()

        # Set up logging level from environment
        log_level = os.getenv("LOG_LEVEL", "INFO")
        logging.getLogger().setLevel(getattr(logging, log_level))

        # Validate required environment variables
        required_vars = ["WP_SITE_URL", "WP_USERNAME", "WP_APP_PASSWORD"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ConfigurationError("Required environment variables are not set")

        # Get and clean up the site URL
        site_url = os.getenv("WP_SITE_URL").strip()

        # Remove any protocol prefix if present
        site_url = site_url.replace("http://", "").replace("https://", "")

        # Remove any trailing slash
        site_url = site_url.rstrip("/")

        # Always use wordpress.com domain
        if not site_url.endswith("wordpress.com"):
            if ".wordpress.com" in site_url:
                # URL contains wordpress.com somewhere incorrectly
                site_url = site_url.replace(".wordpress.com", "")
                site_url = f"{site_url}.wordpress.com"
            else:
                site_url = f"{site_url}.wordpress.com"

        # Now add the protocol
        self.site_url = f"https://{site_url}"

        logger.debug(f"Using WordPress.com site URL: {self.site_url}")

        # Set up authentication
        self.username = os.getenv("WP_USERNAME")
        self.app_password = os.getenv("WP_APP_PASSWORD")

        # Set up basic authentication header with additional headers
        auth_string = f"{self.username}:{self.app_password}"
        self.auth_header = {
            "Authorization": f"Basic {b64encode(auth_string.encode()).decode()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "WordPressBackup/2.0",
        }

        self.backup_dir = Path(os.getenv("BACKUP_DIR", "./backups"))

        # Create backup directory structure
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            self.media_dir = self.backup_dir / "media"
            self.media_dir.mkdir(exist_ok=True)
        except PermissionError:
            raise ConfigurationError(
                f"Cannot create backup directory at {self.backup_dir}. "
                "Please check permissions or specify a different BACKUP_DIR in .env"
            )

        # Initialize containers for relationships
        self.categories = {}
        self.tags = {}
        self.media = {}
        self.authors = {}

        # Rate limiting configuration
        self.rate_limit_delay = float(os.getenv("RATE_LIMIT_DELAY", "0.5"))

    def fetch_all_items(self, endpoint, params=None):
        """Fetch all items from a paginated endpoint with better error handling"""
        if params is None:
            params = {}

        items = []
        page = 1
        per_page = 20  # Reduced batch size

        # First, try to get headers to determine total pages
        try:
            test_params = {"per_page": 1, "page": 1, **params}
            full_url = f"{self.site_url}/wp-json/wp/v2/{endpoint}"
            response = requests.get(
                full_url, headers=self.auth_header, params=test_params, timeout=30
            )

            # Get total pages from WordPress headers
            total_items = int(response.headers.get("X-WP-Total", 0))
            total_pages = int(response.headers.get("X-WP-TotalPages", 0))

            logger.debug(
                f"Found {total_items} total items across {total_pages} pages for {endpoint}"
            )
        except Exception as e:
            logger.warning(f"Could not determine total pages for {endpoint}: {str(e)}")
            total_pages = None

        while True:
            current_params = {"page": page, "per_page": per_page, **params}

            try:
                full_url = f"{self.site_url}/wp-json/wp/v2/{endpoint}"
                logger.debug(f"Fetching page {page} from {full_url}")

                response = requests.get(
                    full_url,
                    headers=self.auth_header,
                    params=current_params,
                    timeout=30,
                )

                # If we get a 400 error and we know the total pages, it means we're done
                if response.status_code == 400 and total_pages and page > total_pages:
                    logger.debug(f"Reached end of pages for {endpoint}")
                    break

                response.raise_for_status()
                page_items = response.json()

                if not page_items:
                    break

                items.extend(page_items)
                logger.debug(
                    f"Fetched {len(page_items)} items from {endpoint} (page {page})"
                )

                # If we know total pages and we've reached it, stop
                if total_pages and page >= total_pages:
                    break

                page += 1

                # Respect rate limiting
                time.sleep(self.rate_limit_delay)

            except requests.exceptions.RequestException as e:
                if "400 Client Error: Bad Request" in str(e):
                    # We've reached the end of available pages
                    logger.debug(f"Reached end of available pages for {endpoint}")
                    break
                else:
                    logger.error(f"Error fetching items from {endpoint}: {str(e)}")
                    if page == 1:
                        # If we fail on the first page, something is wrong
                        raise
                    else:
                        # If we fail after getting some data, return what we have
                        break

        logger.info(f"Successfully fetched {len(items)} items from {endpoint}")
        return items

    def fetch_taxonomies(self):
        """Fetch all categories and tags"""
        logger.info("Fetching taxonomies...")

        try:
            # Fetch categories
            categories = self.fetch_all_items("categories")
            self.categories = {cat["id"]: cat for cat in categories}
            logger.info(f"Fetched {len(self.categories)} categories")

            # Fetch tags
            tags = self.fetch_all_items("tags")
            self.tags = {tag["id"]: tag for tag in tags}
            logger.info(f"Fetched {len(self.tags)} tags")

            # Save taxonomy data
            taxonomy_file = self.backup_dir / "taxonomies.json"
            with open(taxonomy_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"categories": self.categories, "tags": self.tags},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

        except Exception as e:
            logger.error(f"Error fetching taxonomies: {str(e)}")
            raise

    def fetch_authors(self):
        """Fetch all authors/users"""
        logger.info("Fetching authors...")

        try:
            authors = self.fetch_all_items("users")
            self.authors = {author["id"]: author for author in authors}
            logger.info(f"Fetched {len(self.authors)} authors")

            # Save authors data
            authors_file = self.backup_dir / "authors.json"
            with open(authors_file, "w", encoding="utf-8") as f:
                json.dump(self.authors, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error fetching authors: {str(e)}")
            raise

    def fetch_media(self):
        """Fetch all media items"""
        logger.info("Fetching media information...")

        try:
            media_items = self.fetch_all_items("media")
            self.media = {item["id"]: item for item in media_items}
            logger.info(f"Fetched {len(self.media)} media items")

            # Save media metadata
            media_file = self.backup_dir / "media.json"
            with open(media_file, "w", encoding="utf-8") as f:
                json.dump(self.media, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error fetching media: {str(e)}")
            raise

    def get_all_posts(self):
        """Fetch all posts with complete metadata"""
        logger.info("Fetching posts...")
        posts = []

        try:
            posts = self.fetch_all_items(
                "posts",
                {
                    "status": "publish",  # Start with just published posts
                    "_fields": "id,date,modified,slug,title,content,excerpt,status,categories,tags,author,featured_media,comment_status,ping_status,sticky,template,meta,guid,type,format,link",
                },
            )

            logger.info(f"Total posts fetched: {len(posts)}")
            return posts

        except Exception as e:
            logger.error(f"Error fetching posts: {str(e)}")
            return posts

    def save_post(self, post):
        """Save a single post with all metadata"""
        try:
            # Extract date for directory structure
            date = datetime.fromisoformat(post["date"].replace("Z", "+00:00"))
            year_dir = self.backup_dir / str(date.year)
            month_dir = year_dir / f"{date.month:02d}"
            month_dir.mkdir(parents=True, exist_ok=True)

            # Create filename from slug
            filename = f"{post['slug']}.md"
            filepath = month_dir / filename

            # Prepare metadata
            metadata = {
                "id": post["id"],
                "title": post["title"]["rendered"],
                "date": post["date"],
                "modified": post["modified"],
                "slug": post["slug"],
                "status": post["status"],
                "type": post.get("type", "post"),
                "link": post.get("link", ""),
                "format": post.get("format", "standard"),
                "author": self.authors.get(post["author"]),
                "categories": [
                    self.categories.get(cat_id) for cat_id in post.get("categories", [])
                ],
                "tags": [self.tags.get(tag_id) for tag_id in post.get("tags", [])],
                "featured_media": self.media.get(post.get("featured_media")),
                "comment_status": post.get("comment_status", "closed"),
                "ping_status": post.get("ping_status", "closed"),
                "sticky": post.get("sticky", False),
                "template": post.get("template", ""),
                "meta": post.get("meta", {}),
                "excerpt": post["excerpt"]["rendered"],
            }

            # Check if DOWNLOAD_MEDIA is set to true
            if os.getenv("DOWNLOAD_MEDIA", "false").lower() == "true":
                # Download featured media
                featured_media = post.get("featured_media")
                if featured_media:
                    media_item = self.media.get(featured_media)
                    if media_item:
                        media_url = media_item["source_url"]
                        media_filename = os.path.basename(urlparse(media_url).path)
                        media_path = self.media_dir / media_filename
                        try:
                            response = requests.get(media_url, headers=self.auth_header)
                            response.raise_for_status()
                            with open(media_path, "wb") as f:
                                f.write(response.content)
                            metadata["featured_media"] = media_filename
                        except Exception as e:
                            logger.error(
                                f"Error downloading media {media_url}: {str(e)}"
                            )

            # Create post content with frontmatter
            post_content = frontmatter.Post(
                content=post["content"]["rendered"], **metadata
            )

            # Save to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post_content))

            return filepath

        except Exception as e:
            logger.error(f"Error saving post {post.get('id', 'unknown')}: {str(e)}")
            raise

    def backup(self):
        """Main backup process"""
        logger.info(f"Starting WordPress backup for site: {self.site_url}")
        start_time = time.time()

        try:
            # Fetch all supporting data first
            self.fetch_taxonomies()
            self.fetch_authors()
            self.fetch_media()

            # Get all posts
            posts = self.get_all_posts()
            logger.info(f"Found {len(posts)} posts to backup")

            # Save metadata about the backup
            metadata = {
                "backup_date": datetime.now().isoformat(),
                "total_posts": len(posts),
                "site_url": self.site_url,
                "backup_version": "2.0",
                "stats": {
                    "categories": len(self.categories),
                    "tags": len(self.tags),
                    "authors": len(self.authors),
                    "media": len(self.media),
                },
            }

            with open(self.backup_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # Save each post
            for i, post in enumerate(posts, 1):
                try:
                    filepath = self.save_post(post)
                    logger.info(f"[{i}/{len(posts)}] Saved: {filepath}")
                except Exception as e:
                    logger.error(
                        f"Failed to save post {post.get('id', 'unknown')}: {str(e)}"
                    )
                    continue

            elapsed_time = time.time() - start_time
            logger.info(f"\nBackup completed in {elapsed_time:.2f} seconds!")
            logger.info(f"Backup directory: {self.backup_dir}")

        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            raise


def main():
    try:
        logger.info("Starting WordPress backup process...")
        logger.info("Checking configuration...")

        backup = WordPressBackup()
        backup.backup()

        logger.info("Backup completed successfully!")

    except ConfigurationError as e:
        logger.error(f"Configuration Error: {str(e)}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error: Could not connect to WordPress.com. {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug("Full error details:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
