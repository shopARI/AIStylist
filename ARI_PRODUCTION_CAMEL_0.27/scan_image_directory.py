#!/usr/bin/env python3
"""
Image Directory Scanner - Auto-discovery for ShopAri Image Paths
Scans https://app.shopari.com/images/ to build filename -> full_path mapping
"""

import asyncio
import aiohttp
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, List
import re
from urllib.parse import urljoin, urlparse
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("image_scanner")

# Load environment
load_dotenv()

class ImageDirectoryScanner:
    """Scans ShopAri image directories to build filename mappings"""

    def __init__(self, base_url: str = "https://app.shopari.com/images/"):
        self.base_url = base_url.rstrip('/') + '/'
        self.filename_map: Dict[str, str] = {}  # filename -> full_path
        self.discovered_dirs: Set[str] = set()
        self.discovered_files: Set[str] = set()

    async def discover_directories(self, session: aiohttp.ClientSession, max_depth: int = 3) -> List[str]:
        """
        Discover directory structure by crawling the image server
        This assumes directory listing is enabled or we can guess common patterns
        """
        directories = []

        # Try common UUID-like directory patterns (based on your example)
        # bebfd6e9-d390-4f3e-b0fb-f3a1e4ddec49/b5a77d71-43bd-420c-9edd-71e198589d35/

        logger.info("Search Starting directory discovery...")

        # First, try to get a directory listing of the root
        try:
            async with session.get(self.base_url) as response:
                if response.status == 200:
                    content = await response.text()
                    # Look for directory links in HTML
                    dir_pattern = re.findall(r'href="([a-f0-9-]{36})/?["\s]', content, re.IGNORECASE)
                    directories.extend(dir_pattern)
                    logger.info(f"Directory Found {len(dir_pattern)} root directories from listing")
        except Exception as e:
            logger.warning(f"Warning Could not get directory listing: {e}")

        # If no directories found, try some heuristic approaches
        if not directories:
            logger.info("Target Trying heuristic directory discovery...")

            # Sample some known patterns or use brute force on common UUID patterns
            # This is a fallback - in production you might have a better way to discover dirs
            sample_dirs = [
                "bebfd6e9-d390-4f3e-b0fb-f3a1e4ddec49",
                "000005c0-693f-4352-90fd-60f87eb6d8a2",
                # Add more if you know some existing directory names
            ]

            for sample_dir in sample_dirs:
                try:
                    test_url = f"{self.base_url}{sample_dir}/"
                    async with session.get(test_url) as response:
                        if response.status == 200:
                            directories.append(sample_dir)
                            logger.info(f"Success Confirmed directory: {sample_dir}")
                except Exception:
                    continue

        return directories

    async def scan_directory_recursive(self, session: aiohttp.ClientSession, dir_path: str) -> List[str]:
        """Recursively scan a directory for image files"""
        files_found = []

        try:
            dir_url = f"{self.base_url}{dir_path}/"
            async with session.get(dir_url) as response:
                if response.status == 200:
                    content = await response.text()

                    # Look for image files
                    image_pattern = re.findall(
                        r'href="([^"]*\.(jpg|jpeg|png|gif|webp))"',
                        content,
                        re.IGNORECASE
                    )

                    for match in image_pattern:
                        filename = match[0]
                        full_path = f"{dir_path}/{filename}"
                        files_found.append(full_path)

                        # Store in filename map
                        base_filename = filename.split('/')[-1]  # Just the filename
                        self.filename_map[base_filename] = full_path

                    # Look for subdirectories
                    subdir_pattern = re.findall(r'href="([a-f0-9-]{36})/?["\s]', content, re.IGNORECASE)
                    for subdir in subdir_pattern:
                        if subdir not in self.discovered_dirs:
                            self.discovered_dirs.add(subdir)
                            subdir_path = f"{dir_path}/{subdir}"
                            sub_files = await self.scan_directory_recursive(session, subdir_path)
                            files_found.extend(sub_files)

                            # Small delay to be nice to the server
                            await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"Warning Error scanning directory {dir_path}: {e}")

        return files_found

    async def scan_with_sitemap_approach(self, session: aiohttp.ClientSession) -> Dict[str, str]:
        """
        Alternative: Try to find a sitemap or index that lists all images
        """
        sitemap_urls = [
            f"{self.base_url}sitemap.xml",
            f"{self.base_url}index.html",
            f"{self.base_url}list.json",
        ]

        for sitemap_url in sitemap_urls:
            try:
                async with session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Success Found sitemap/index at: {sitemap_url}")

                        # Extract all image URLs
                        image_urls = re.findall(
                            r'(https?://[^\s<>"]+\.(jpg|jpeg|png|gif|webp))',
                            content,
                            re.IGNORECASE
                        )

                        for url_match in image_urls:
                            full_url = url_match[0]
                            if self.base_url in full_url:
                                # Extract relative path
                                relative_path = full_url.replace(self.base_url, '')
                                filename = relative_path.split('/')[-1]
                                self.filename_map[filename] = relative_path

                        logger.info(f"Stats Extracted {len(self.filename_map)} images from sitemap")
                        return self.filename_map

            except Exception as e:
                logger.debug(f"Warning Sitemap {sitemap_url} not available: {e}")
                continue

        return {}

    async def scan_from_neo4j_sample(self, session: aiohttp.ClientSession) -> Dict[str, str]:
        """
        Alternative approach: Extract filenames from Neo4j and try to find them
        """
        try:
            from neo4j import GraphDatabase

            # Connect to Neo4j
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                auth=(
                    os.getenv("NEO4J_USERNAME", "neo4j"),
                    os.getenv("NEO4J_PASSWORD", "")
                )
            )

            logger.info("Search Extracting filenames from Neo4j sample...")

            # Get sample of image URLs
            with driver.session() as neo_session:
                result = neo_session.run("""
                    MATCH (p:Product)
                    WHERE p.images IS NOT NULL
                    RETURN p.images
                    LIMIT 100
                """)

                shopify_filenames = []
                for record in result:
                    images_data = record[0]  # Get first column value
                    if isinstance(images_data, str):
                        try:
                            images_data = json.loads(images_data)
                        except:
                            images_data = [images_data]

                    for img_url in images_data:
                        if 'shopify.com' in img_url:
                            # Extract filename from Shopify URL
                            filename_match = re.search(r'/([^/]+\.(jpg|jpeg|png|gif|webp))(\?|$)', img_url, re.IGNORECASE)
                            if filename_match:
                                filename = filename_match.group(1)
                                shopify_filenames.append(filename)

                logger.info(f"📦 Found {len(shopify_filenames)} filenames from Neo4j")

                # Now try to find these files in the directory structure
                found_mappings = {}

                # Try some common directory patterns
                test_dirs = await self.discover_directories(session)

                for filename in shopify_filenames[:20]:  # Test first 20
                    logger.info(f"Search Searching for: {filename}")

                    # Try different directory combinations
                    for dir1 in test_dirs:
                        for subdir in ["", "images", "products", "uploads"]:  # Common subdirs
                            if subdir:
                                test_path = f"{dir1}/{subdir}/{filename}"
                                test_url = f"{self.base_url}{test_path}"
                            else:
                                test_path = f"{dir1}/{filename}"
                                test_url = f"{self.base_url}{test_path}"

                            try:
                                async with session.head(test_url) as response:
                                    if response.status == 200 and response.headers.get('content-type', '').startswith('image/'):
                                        found_mappings[filename] = test_path
                                        logger.info(f"Success Found: {filename} -> {test_path}")
                                        break
                            except:
                                continue

                        if filename in found_mappings:
                            break

                    # Rate limiting
                    await asyncio.sleep(0.2)

                return found_mappings

        except Exception as e:
            logger.error(f"Error Neo4j scanning failed: {e}")
            return {}

    async def full_scan(self) -> Dict[str, str]:
        """Perform complete directory scan using multiple approaches"""
        logger.info(f"Starting Starting full image directory scan of {self.base_url}")
        start_time = time.time()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:

            # Approach 1: Try sitemap/index files
            logger.info("📋 Trying sitemap approach...")
            sitemap_results = await self.scan_with_sitemap_approach(session)
            if sitemap_results:
                self.filename_map.update(sitemap_results)

            # Approach 2: Neo4j guided search (most practical)
            logger.info("Target Trying Neo4j-guided search...")
            neo4j_results = await self.scan_from_neo4j_sample(session)
            if neo4j_results:
                self.filename_map.update(neo4j_results)

            # Approach 3: Directory crawling (if server allows)
            if len(self.filename_map) < 10:  # If other methods didn't work well
                logger.info("🕷️ Trying directory crawling...")
                directories = await self.discover_directories(session)

                for directory in directories:
                    logger.info(f"Directory Scanning directory: {directory}")
                    await self.scan_directory_recursive(session, directory)
                    await asyncio.sleep(0.5)  # Rate limiting

        elapsed_time = time.time() - start_time
        logger.info(f"Stats Scan completed in {elapsed_time:.1f}s")
        logger.info(f"Success Discovered {len(self.filename_map)} filename mappings")

        return self.filename_map

    def save_mapping(self, filepath: str = "image_filename_mapping.json"):
        """Save the filename mapping to a JSON file"""
        mapping_data = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total_files": len(self.filename_map),
            "mappings": self.filename_map
        }

        with open(filepath, 'w') as f:
            json.dump(mapping_data, f, indent=2)

        logger.info(f"Saving Saved {len(self.filename_map)} mappings to: {filepath}")

    @classmethod
    def load_mapping(cls, filepath: str = "image_filename_mapping.json") -> Dict[str, str]:
        """Load filename mapping from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            logger.info(f"📂 Loaded {data['total_files']} mappings from: {filepath}")
            return data['mappings']

        except FileNotFoundError:
            logger.warning(f"Warning Mapping file not found: {filepath}")
            return {}
        except Exception as e:
            logger.error(f"Error Error loading mapping: {e}")
            return {}

async def main():
    """Main scanning function"""
    scanner = ImageDirectoryScanner()

    # Perform the scan
    mappings = await scanner.full_scan()

    # Save results
    scanner.save_mapping()

    # Show sample results
    if mappings:
        logger.info("Target Sample mappings found:")
        for i, (filename, path) in enumerate(list(mappings.items())[:5]):
            logger.info(f"   {filename} -> {path}")
        logger.info(f"   ... and {len(mappings)-5} more")
    else:
        logger.warning("Warning No mappings discovered. Check server access or directory structure.")

    return mappings

if __name__ == "__main__":
    results = asyncio.run(main())