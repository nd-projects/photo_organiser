# Quickstart Guide: Photo Album Organization Application

**Last Updated**: 2025-10-16

This guide will help you set up the development environment and run the photo album organization application.

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ or Debian 11+)
- **Python**: 3.13 or higher
- **System Libraries**:
  - `libraw` (for RAW image support)
  - PyQt6 dependencies (installed automatically with pip)

### Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install libraw-dev

# Verify Python version
python3 --version  # Should be 3.13+
```

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd photo_organiser
```

### 2. Install uv Package Manager

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 3. Create Virtual Environment and Install Dependencies

```bash
# Create virtual environment and install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### 4. Configure Application

Create a configuration file (optional, can also use CLI argument):

```bash
# Create data directory
mkdir -p data

# Configure photo directory path
# Option 1: Environment variable
export PHOTO_DIR="/media/nick/Photo_Backups/Camera_Photos"

# Option 2: Edit config file (future feature)
# echo "photo_dir = '/path/to/photos'" > config.toml
```

## Running the Application

### Development Mode

```bash
# Run with default photo directory from environment
uv run python src/main.py

# Or specify photo directory as argument
uv run python src/main.py --photo-dir /path/to/photos
```

### Production Mode

```bash
# Build and install
uv build
uv tool install .

# Run installed version
photo-organiser --photo-dir /path/to/photos
```

## Project Structure

```text
photo_organiser/
├── src/                          # Source code
│   ├── models/                   # Data models
│   │   ├── album.py             # Album entity
│   │   ├── photo.py             # Photo entity
│   │   └── app_state.py         # Application state
│   ├── services/                 # Business logic
│   │   ├── filesystem_scanner.py    # Directory scanning
│   │   ├── filesystem_watcher.py    # File change monitoring
│   │   ├── photo_processor.py       # Image processing
│   │   ├── album_manager.py         # Album operations
│   │   └── photo_manager.py         # Photo operations
│   ├── ui/                       # User interface
│   │   ├── main_window.py       # Main application window
│   │   ├── album_grid.py        # Album grid view
│   │   ├── photo_grid.py        # Photo grid view
│   │   ├── lightbox.py          # Photo lightbox modal
│   │   └── widgets/             # UI components
│   ├── utils/                    # Utilities
│   │   ├── exif_parser.py       # EXIF metadata
│   │   ├── file_validator.py    # File validation
│   │   └── thumbnail_cache.py   # Thumbnail caching
│   └── main.py                   # Application entry point
├── tests/                        # Test files
│   ├── test_photo_processor.py  # Image processing tests
│   ├── test_file_operations.py  # File operation tests
│   └── test_filesystem_scanner.py   # Scanning tests
├── data/                         # Application data
│   ├── thumbnails/              # Thumbnail cache
│   └── app.db                   # SQLite database
├── specs/                        # Specifications
│   └── 001-build-an-application/ # Current feature
│       ├── spec.md              # Feature specification
│       ├── plan.md              # Implementation plan
│       ├── research.md          # Technical research
│       ├── data-model.md        # Data model
│       ├── quickstart.md        # This file
│       └── contracts/           # API contracts
├── pyproject.toml               # Project configuration
└── README.md                    # Project overview
```

## Key Features

### Album Management

- **View Albums**: Browse all photo albums in a chronological grid
- **Open Album**: Click any album to view its photos
- **Reorder Albums**: Drag and drop albums to custom positions
- **Create Album**: Create new empty albums for organization
- **Rename Album**: Give albums meaningful names

### Photo Management

- **View Photos**: Browse photos in a tile grid within an album
- **Lightbox View**: Click photos to view full-size in a modal overlay
- **Select Photos**: Drag across multiple photos to select them
- **Move Photos**: Move selected photos between albums
- **RAW-JPEG Deduplication**: Automatically shows one tile for RAW+JPEG pairs

### Automatic Features

- **Filesystem Watching**: Detects external changes and refreshes automatically
- **Thumbnail Caching**: Generates thumbnails on-demand and caches them
- **EXIF Metadata**: Extracts and displays photo dates from EXIF data
- **Date Parsing**: Automatically extracts dates from folder names

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_photo_processor.py
```

### Linting and Formatting

```bash
# Run ruff linter
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/
```

### Adding Dependencies

```bash
# Add a runtime dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Update all dependencies
uv sync --upgrade
```

## Configuration

### Photo Directory

The application needs to know where your photos are stored. You can specify this in three ways:

1. **Command-line argument** (highest priority):

   ```bash
   uv run python src/main.py --photo-dir /path/to/photos
   ```

2. **Environment variable**:

   ```bash
   export PHOTO_DIR="/path/to/photos"
   uv run python src/main.py
   ```

3. **Interactive prompt** (fallback):
   If neither is provided, the application will prompt you to select a directory on first launch.

### Thumbnail Cache

Thumbnails are cached in `data/thumbnails/` by default. To change this:

```bash
# Use custom cache directory
uv run python src/main.py --cache-dir /path/to/cache
```

To clear the cache:

```bash
rm -rf data/thumbnails/*
```

### Database

Application state is stored in `data/app.db` (SQLite). To reset:

```bash
# Backup current state
cp data/app.db data/app.db.backup

# Reset database (will lose custom album ordering)
rm data/app.db
```

## Keyboard Shortcuts

### Global

- `Ctrl+Q`: Quit application
- `Escape`: Go back / Close modal
- `F11`: Toggle fullscreen

### Album View

- `Arrow keys`: Navigate between albums
- `Enter`: Open selected album
- `Ctrl+N`: Create new album
- `F2`: Rename selected album

### Photo View

- `Arrow keys`: Navigate between photos
- `Space`: Open photo in lightbox
- `Ctrl+A`: Select all photos
- `Ctrl+D`: Deselect all
- `Delete`: Move selected photos to trash (future feature)

### Lightbox

- `Escape` / `Q`: Close lightbox
- `Arrow Left/Right`: Previous/Next photo
- `+/-`: Zoom in/out (future feature)

## Troubleshooting

### Issue: "Cannot load RAW images"

**Solution**: Install libraw development package

```bash
sudo apt install libraw-dev
pip install rawpy --force-reinstall
```

### Issue: "Permission denied" when moving photos

**Solution**: Check filesystem permissions on photo directory

```bash
chmod -R u+rw /path/to/photos
```

### Issue: Thumbnails not generating

**Solution**: Ensure cache directory is writable

```bash
mkdir -p data/thumbnails
chmod u+rw data/thumbnails
```

### Issue: High memory usage

**Solution**: Clear thumbnail cache and restart

```bash
rm -rf data/thumbnails/*
```

### Issue: Slow album loading

**Possible causes**:

1. Very large albums (>1000 photos) - normal, uses virtual scrolling
2. Network-mounted drive - copy photos locally for better performance
3. Corrupted EXIF data - check logs for warnings

## Performance Tips

1. **Local Storage**: Keep photos on local SSD/HDD for best performance
2. **Thumbnail Cache**: Keep cache on same drive as application
3. **Album Size**: Organize into albums of <500 photos for optimal experience
4. **RAW Files**: Consider keeping only JPEG versions if not editing
5. **File Formats**: JPEG/PNG load fastest; RAW files require decoding

## Next Steps

- Read the [Feature Specification](spec.md) for detailed requirements
- Review the [Data Model](data-model.md) for entity relationships
- Check the [Implementation Plan](plan.md) for architecture overview
- Run `/speckit.tasks` to generate implementation tasks

## Getting Help

- Check the [GitHub Issues](../../issues) for known problems
- Review logs in `data/logs/` for error details
- Enable debug mode: `uv run python src/main.py --debug`

---

**Ready to start developing?** Run `uv run python src/main.py` and point it to your photo directory!
