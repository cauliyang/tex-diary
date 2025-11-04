#!/usr/bin/env python3
"""
LaTeX to LaTeX Converter
========================

Converts LaTeX files to use the entry template structure while preserving content.
Extracts content from \begin{document}...\end{document} and applies the entry template.

Usage:
    ./tex2tex_convert.py input_folder [output_folder] [options]
    ./tex2tex_convert.py posts/2024/ converted_2024/ --verbose
"""

import argparse
import sys
import os
import re
import yaml
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime


class Tex2TexConverter:
    """LaTeX to LaTeX converter with template application"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config = self._load_config()
        self.template = self._load_template()

    def log(self, message: str, level: str = "INFO"):
        """Logging with optional verbosity"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"{level}: {message}")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.yaml"""
        config_path = Path(__file__).parent / "config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self.log(f"Loaded config from {config_path}")
            return config
        except Exception as e:
            self.log(f"Error loading config: {e}", "ERROR")
            return {}

    def _load_template(self) -> str:
        """Load the entry template"""
        template_path = (
            Path(__file__).parent
            / "assets"
            / "templates"
            / "entries"
            / "entry_template.tex"
        )
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
            self.log(f"Loaded template from {template_path}")
            return template
        except Exception as e:
            self.log(f"Error loading template: {e}", "ERROR")
            return ""

    def find_tex_files(self, input_folder: Path) -> List[Path]:
        """Find all .tex files in the input folder"""
        tex_files = list(input_folder.glob("*.tex"))
        self.log(f"Found {len(tex_files)} .tex files in {input_folder}")
        return tex_files

    def extract_content(self, tex_file: Path) -> Optional[str]:
        """Extract content between \begin{document} and \end{document}"""
        try:
            with open(tex_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Find the document content
            doc_start = content.find("\\begin{document}")
            doc_end = content.find("\\end{document}")

            if doc_start == -1 or doc_end == -1:
                self.log(f"No document environment found in {tex_file.name}", "WARNING")
                return None

            # Extract content between document tags
            doc_content = content[
                doc_start + len("\\begin{document}") : doc_end
            ].strip()

            # Remove the title line if it exists (the \href{run:...} line)
            doc_content = re.sub(r"\\href\{run:[^}]+\}\{[^}]+\}\s*", "", doc_content)

            # Remove empty sections
            doc_content = re.sub(r"\\section\{\s*\}\s*", "", doc_content)

            self.log(f"Extracted content from {tex_file.name}")
            return doc_content

        except Exception as e:
            self.log(f"Error extracting content from {tex_file.name}: {e}", "ERROR")
            return None

    def get_date_info(self, tex_file: Path) -> Dict[str, str]:
        """Extract date information from filename"""
        filename = tex_file.stem

        # Try to extract date from filename (format: YYYY-MM-DD or similar)
        date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", filename)

        if date_match:
            year, month, day = date_match.groups()
            month_num = int(month)
            day_num = int(day)
        else:
            # Use current date as fallback
            now = datetime.now()
            year = str(now.year)
            month_num = now.month
            day_num = now.day

        # Month names
        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        return {
            "year": year,
            "month": str(month_num),
            "day": str(day_num),
            "month_name": month_names[month_num - 1],
            "day_number": str(day_num),
        }

    def inject_personal_info(
        self, template: str, tex_file: Path, folder_name: str
    ) -> str:
        """Inject personal information and date into template"""
        date_info = self.get_date_info(tex_file)

        # Personal information from config
        author = self.config.get("author", "Unknown Author")
        institution = self.config.get("institution", "Unknown Institution")
        diary_title = self.config.get("diary_title", "Research Diary")

        # Replace placeholders in template
        replacements = {
            "<YEAR>": date_info["year"],
            "<MONTH>": date_info["month"],
            "<DAY>": date_info["day"],
            "<MONTH_NAME>": date_info["month_name"],
            "<DAY_NUMBER>": date_info["day_number"],
            "<AUTHOR>": author,
            "<INSTITUTION>": institution,
            "<DIARY_TITLE>": diary_title,
            "<FILENAME>": tex_file.name,
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        # Add folder name as tag
        if "<TAGS>" in result:
            result = result.replace("<TAGS>", folder_name)
        else:
            # Add tags section if not present
            result = result.replace("%<TAGs>: <TAGS>", f"%<TAGs>: {folder_name}")

        return result

    def copy_assets(
        self, tex_file: Path, output_dir: Path, use_symlinks: bool = False
    ) -> List[Path]:
        """Copy or symlink assets referenced in the LaTeX file"""
        copied_files = []

        # Find all asset references in the tex file
        asset_refs = self._find_asset_references(tex_file)

        if not asset_refs:
            self.log("No asset references found")
            return copied_files

        self.log(f"Found {len(asset_refs)} asset references")

        if use_symlinks:
            # Create a single symlink to the entire assets directory
            try:
                # Find the root assets directory
                root_dir = tex_file.parent
                while root_dir.parent != root_dir:  # Not at filesystem root
                    if (root_dir / "assets").exists():
                        break
                    root_dir = root_dir.parent

                original_assets_dir = root_dir / "assets"
                if original_assets_dir.exists():
                    # Create symlink to the entire assets directory
                    assets_symlink = output_dir / "assets"
                    if assets_symlink.exists() or assets_symlink.is_symlink():
                        assets_symlink.unlink()

                    relative_assets = os.path.relpath(original_assets_dir, output_dir)
                    assets_symlink.symlink_to(relative_assets)
                    self.log(f"Created assets symlink: assets -> {relative_assets}")
                    copied_files.append(assets_symlink)
                else:
                    self.log("No assets directory found", "WARNING")
            except OSError as e:
                self.log(f"Failed to create assets symlink: {e}", "WARNING")
                # Fallback to copying individual files
                for asset_path in asset_refs:
                    source_file = self._resolve_asset_path(asset_path, tex_file)
                    if source_file and source_file.exists():
                        dest_file = output_dir / asset_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_file, dest_file)
                        copied_files.append(dest_file)
                        self.log(f"Fallback: Copied asset: {asset_path}")
        else:
            # Copy each referenced asset, preserving relative directory structure
            for asset_path in asset_refs:
                source_file = self._resolve_asset_path(asset_path, tex_file)
                if source_file and source_file.exists():
                    # Preserve the relative path structure from the tex file
                    dest_file = output_dir / asset_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file normally
                    shutil.copy2(source_file, dest_file)
                    copied_files.append(dest_file)
                    self.log(f"Copied asset: {asset_path}")
                else:
                    self.log(f"Asset not found: {asset_path}", "WARNING")

        return copied_files

    def _find_asset_references(self, tex_file: Path) -> List[str]:
        """Find all asset references in the LaTeX file"""
        try:
            with open(tex_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Find various asset reference patterns
            patterns = [
                r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}",
                r"\\input\{([^}]*\.(?:png|jpg|jpeg|pdf|eps|svg))\}",
                r"\\epsfig\{file=([^,}]+)",
                r"\\psfig\{file=([^,}]+)",
            ]

            asset_refs = set()
            for pattern in patterns:
                matches = re.findall(pattern, content)
                asset_refs.update(matches)

            return list(asset_refs)

        except Exception as e:
            self.log(f"Error finding asset references: {e}", "ERROR")
            return []

    def _resolve_asset_path(self, asset_path: str, tex_file: Path) -> Optional[Path]:
        """Resolve an asset path relative to the tex file"""
        # Try different possible locations
        possible_paths = [
            tex_file.parent / asset_path,
            tex_file.parent / "assets" / "figures" / asset_path,
            tex_file.parent / "figures" / asset_path,
            tex_file.parent.parent / "assets" / "figures" / asset_path,
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def convert_file(
        self,
        tex_file: Path,
        output_dir: Path,
        folder_name: str,
        use_symlinks: bool = False,
    ) -> bool:
        """Convert a single .tex file"""
        try:
            # Extract content from original file
            content = self.extract_content(tex_file)
            if content is None:
                return False

            # Get template with personal info injected
            template = self.inject_personal_info(self.template, tex_file, folder_name)

            # Find where to insert the content (after the title line)
            title_line = f"\\href{{run:{tex_file.name}}}{{\\Huge {self.get_date_info(tex_file)['month_name']} {self.get_date_info(tex_file)['day_number']}}}"

            # Insert content after the title line and before bibliography
            if "\\bibliographystyle" in template:
                # Insert content before bibliography
                bib_start = template.find("\\bibliographystyle")
                new_content = (
                    template[:bib_start] + content + "\n\n" + template[bib_start:]
                )
            else:
                # Insert content before \end{document}
                doc_end = template.find("\\end{document}")
                new_content = template[:doc_end] + content + "\n\n" + template[doc_end:]

            # Write converted file
            output_file = output_dir / tex_file.name
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Copy or symlink assets
            if use_symlinks:
                self.log(f"Creating symlinks to assets for {tex_file.name}...")
            else:
                self.log(f"Copying assets for {tex_file.name}...")
            self.copy_assets(tex_file, output_dir, use_symlinks)

            self.log(f"✅ Converted {tex_file.name}")
            return True

        except Exception as e:
            self.log(f"❌ Error converting {tex_file.name}: {e}", "ERROR")
            return False

    def convert_folder(
        self,
        input_folder: Path,
        output_folder: Optional[Path] = None,
        use_symlinks: bool = False,
    ) -> int:
        """Convert all .tex files in a folder"""
        if not input_folder.exists():
            self.log(f"Input folder does not exist: {input_folder}", "ERROR")
            return 1

        # Find all .tex files
        tex_files = self.find_tex_files(input_folder)
        if not tex_files:
            self.log("No .tex files found", "WARNING")
            return 0

        # Set up output folder
        if output_folder is None:
            output_folder = input_folder.parent / f"converted_{input_folder.name}"

        output_folder.mkdir(parents=True, exist_ok=True)
        self.log(f"Output folder: {output_folder}")

        # Get folder name for tagging
        folder_name = input_folder.name

        # Convert each file
        successful = 0
        failed = 0

        for tex_file in tex_files:
            if self.convert_file(tex_file, output_folder, folder_name, use_symlinks):
                successful += 1
            else:
                failed += 1

        # Summary
        self.log(f"\n📊 Conversion Summary:")
        self.log(f"  ✅ Successful: {successful}")
        self.log(f"  ❌ Failed: {failed}")
        self.log(f"  📂 Output: {output_folder}")

        return failed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LaTeX to LaTeX Converter with Template Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./tex2tex_convert.py posts/2024/
  ./tex2tex_convert.py posts/2024/ converted_2024/
  ./tex2tex_convert.py posts/2024/ --symlink-assets
  ./tex2tex_convert.py posts/2024/ --verbose
        """,
    )

    parser.add_argument(
        "input_folder", type=Path, help="Input folder containing .tex files"
    )
    parser.add_argument(
        "output_folder",
        type=Path,
        nargs="?",
        help="Output folder (default: converted_<input_folder_name>)",
    )
    parser.add_argument(
        "--symlink-assets",
        action="store_true",
        help="Create symlinks to assets instead of copying",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Validate input folder
    if not args.input_folder.exists():
        print(f"ERROR: Input folder not found: {args.input_folder}")
        sys.exit(1)

    if not args.input_folder.is_dir():
        print(f"ERROR: Input path is not a directory: {args.input_folder}")
        sys.exit(1)

    # Create converter and convert
    converter = Tex2TexConverter(verbose=args.verbose)

    try:
        failed_count = converter.convert_folder(
            input_folder=args.input_folder,
            output_folder=args.output_folder,
            use_symlinks=args.symlink_assets,
        )

        if failed_count == 0:
            print(f"\n🎉 All conversions completed successfully!")
        else:
            print(f"\n⚠️  {failed_count} conversions failed")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Batch conversion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
