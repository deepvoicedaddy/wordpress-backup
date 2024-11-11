# WordPress.com Blog Backup Tool

A comprehensive Python script to backup all content from a WordPress.com blog into easily manageable files. This tool captures posts, media metadata, taxonomies, and author information in a format suitable for disaster recovery or blog migration.

## Features

### Content Backup
- Complete post content with original formatting
- Post metadata and settings
- Categories and tags
- Author information
- Media metadata
- Featured images data
- Custom fields and templates
- Comments status
- Publication dates and modifications

### Organization
- Posts organized by year/month structure
- Separate JSON files for taxonomies
- Media metadata storage
- Complete backup statistics
- Comprehensive logging

### Technical Features
- Rate limiting to prevent API throttling
- Automatic retry on failed requests
- Progress tracking and logging
- Environment variable configuration
- Error handling and recovery

## Prerequisites

- Python 3.8.1 or higher
- Poetry (Python package manager)
- WordPress.com blog with API access
- Application password from WordPress.com

## Installation

1. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Clone this repository:
```bash
git clone https://github.com/deepvoicedaddy/wordpressdotcom-backup.git
cd wordpressdotcom-backup
```

3. Install dependencies using Poetry:
```bash
poetry install
```

## Configuration

1. Create your environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your WordPress.com credentials:
```env
# WordPress.com credentials
WP_SITE_URL=yourblog.wordpress.com
WP_USERNAME=your_username
WP_APP_PASSWORD=your_app_password

# Backup settings
BACKUP_DIR=./backups

# Optional settings
LOG_LEVEL=INFO
DOWNLOAD_MEDIA=false
RATE_LIMIT_DELAY=0.5
```

### Getting Your WordPress.com Application Password

1. Log in to WordPress.com
2. Go to Account Settings → Security → Application Passwords
3. Create a new application password for this backup tool
4. Copy the generated password to your `.env` file

## Usage

Run the backup using Poetry:
```bash
poetry run python wp_backup.py
```

Or activate the virtual environment and run:
```bash
poetry shell
python wp_backup.py
```

## Backup Structure

The script creates the following directory structure:
```
backups/
  ├── metadata.json         # Backup metadata and statistics
  ├── taxonomies.json      # Categories and tags
  ├── authors.json        # Author information
  ├── media.json         # Media metadata
  ├── 2024/
  │   ├── 01/
  │   │   ├── post-title-1.md
  │   │   └── post-title-2.md
  │   └── 02/
  │       └── post-title-3.md
```

### Post File Format

Each post is saved as a markdown file with frontmatter metadata:
```markdown
---
title: Post Title
date: 2024-01-01T12:00:00Z
modified: 2024-01-01T12:00:00Z
slug: post-title
status: publish
categories:
  - Category 1
  - Category 2
tags:
  - Tag 1
  - Tag 2
author:
  id: 1
  name: Author Name
featured_media:
  id: 123
  url: https://example.com/image.jpg
---

Post content goes here...
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Style

Format code using Black:
```bash
poetry run black .
```

Run linting:
```bash
poetry run flake8
```

## Disaster Recovery

To restore your blog using these backups:

1. Each post file contains complete metadata in its frontmatter
2. Use WordPress's import functionality or the REST API to restore posts
3. Metadata files (taxonomies.json, authors.json) contain relationship data
4. Media files can be re-uploaded using the metadata in media.json

## Troubleshooting

### Common Issues

1. API Rate Limiting
   - Adjust RATE_LIMIT_DELAY in .env
   - Default delay is 0.5 seconds between requests

2. Authentication Failures
   - Verify your application password
   - Ensure your WordPress.com account has appropriate permissions

3. Incomplete Backups
   - Check the logs for specific errors
   - Verify your WordPress.com API access

### Debug Logging

Enable detailed logging by setting in .env:
```env
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details.

## Author

Deep Voice Daddy
https://github.com/deepvoicedaddy

## Support

- Open an issue on GitHub
- Check the [WordPress.com REST API documentation](https://developer.wordpress.com/docs/api/)
- Review the [Python Requests library documentation](https://requests.readthedocs.io/)