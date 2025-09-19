#!/usr/bin/env python3
"""
Python Project Dependency Analyzer - Final Production Version
Designed for projects where flat files will become nested folders.
E.g., agents_base_py.py -> agents/base.py
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
import argparse


class DependencyAnalyzer:
    def __init__(self, root_dir=".", verbose=False):
        self.root_dir = Path(root_dir).resolve()  # Resolve to absolute path
        self.verbose = verbose
        
        # Core data structures
        self.files = {}  # filename -> file info
        self.dependencies = defaultdict(set)  # file -> set of files it depends on
        self.imported_by = defaultdict(set)  # file -> set of files that import it
        self.external_deps = defaultdict(set)  # file -> external packages
        
        # Build mapping of how imports resolve to actual files
        self.import_to_file = {}  # "agents.base" -> "agents_base_py.py"
        self.file_to_imports = defaultdict(set)  # "agents_base_py.py" -> {"agents.base", "agents_base"}
        
    def analyze(self):
        """Main analysis pipeline."""
        print("Starting dependency analysis...", file=sys.stderr)
        
        # Step 1: Discover all Python files
        py_files = self.discover_files()
        if not py_files:
            return " No Python files found in the specified directory!"
        
        print(f"Found {len(py_files)} Python files", file=sys.stderr)
        
        # Step 2: Build import mappings
        if self.verbose:
            print("Building import mappings...", file=sys.stderr)
        self.build_import_mappings(py_files)
        
        # Step 3: Parse each file and extract dependencies
        if self.verbose:
            print("Parsing files and extracting dependencies...", file=sys.stderr)
        for py_file in py_files:
            self.parse_file(py_file)
        
        # Step 4: Generate report
        if self.verbose:
            print("Generating report...", file=sys.stderr)
        return self.generate_report()
    
    def discover_files(self):
        """Find all Python files in the project."""
        if not self.root_dir.exists():
            print(f"Error: Directory {self.root_dir} does not exist!", file=sys.stderr)
            return []
            
        py_files = []
        try:
            for path in self.root_dir.rglob("*.py"):
                # Convert to string for checking
                path_str = str(path)
                path_parts = path_str.replace('\\', '/').split('/')
                
                # Skip virtual environments and special directories
                skip_dirs = {
                    'venv', 'env', '.venv', '.env',
                    '__pycache__', 'site-packages',
                    '.git', 'build', 'dist',
                    '.tox', '.pytest_cache', 'node_modules'
                }
                
                # Check if any part of the path is in skip_dirs
                if any(part in skip_dirs for part in path_parts):
                    continue
                
                # Skip specific files
                if path.name in ['dependency_analyzer.py', 'setup.py']:
                    continue
                
                # Skip compiled Python files
                if path.suffix in ['.pyc', '.pyo']:
                    continue
                    
                # Skip if file is empty
                try:
                    if path.stat().st_size == 0:
                        if self.verbose:
                            print(f"  Skipping empty file: {path.name}", file=sys.stderr)
                        continue
                except Exception as e:
                    if self.verbose:
                        print(f"  Cannot stat file {path.name}: {e}", file=sys.stderr)
                    continue
                    
                py_files.append(path)
                
        except Exception as e:
            print(f"Error discovering files: {e}", file=sys.stderr)
            
        return py_files
    
    def build_import_mappings(self, py_files):
        """Build bidirectional mappings between import names and actual files.
        
        Key insight: agents_base_py.py is imported as "agents.base"
        """
        for py_file in py_files:
            try:
                rel_path = str(py_file.relative_to(self.root_dir))
            except ValueError:
                # File is outside root_dir somehow
                continue
                
            # Normalize path separators to forward slashes
            rel_path = rel_path.replace('\\', '/')
            
            # Store file info
            self.files[rel_path] = {
                'path': py_file,
                'lines': 0  # Will be updated when parsing
            }
            
            # Generate all possible import names for this file
            import_names = self.generate_import_names(rel_path)
            
            for import_name in import_names:
                # Handle potential conflicts (two files mapping to same import)
                if import_name in self.import_to_file:
                    existing = self.import_to_file[import_name]
                    if existing != rel_path:  # Different file with same import name
                        if self.verbose:
                            print(f"  ⚠️  Import conflict: '{import_name}'", file=sys.stderr)
                            print(f"      Existing: {existing}", file=sys.stderr)
                            print(f"      New:      {rel_path}", file=sys.stderr)
                            print(f"      Keeping:  {existing} (first encountered)", file=sys.stderr)
                else:
                    self.import_to_file[import_name] = rel_path
                    
                self.file_to_imports[rel_path].add(import_name)
                
                if self.verbose and import_names:
                    # Show only first few to avoid spam
                    display_names = import_names[:3]
                    names_str = ', '.join(f"'{n}'" for n in display_names)
                    if len(import_names) > 3:
                        names_str += f' (+{len(import_names)-3} more)'
                    print(f"  {rel_path} -> {names_str}", file=sys.stderr)
    
    def generate_import_names(self, filepath):
        """Generate all possible ways this file might be imported.
        
        Examples:
        - agents_base_py.py -> agents.base, agents_base
        - services_battle_cache_py.py -> services.battle.cache, services.battle_cache
        - lib_camel_v070_init_py.py -> lib.camel.v070
        """
        import_names = set()
        
        # Remove .py extension
        name = filepath[:-3] if filepath.endswith('.py') else filepath
        
        # Normalize path separators (in case of subdirectories)
        name = name.replace('\\', '/').replace('/', '.')
        
        # Always include the exact name (minus .py)
        import_names.add(name)
        
        # If it ends with _py, that's our special pattern
        if name.endswith('_py'):
            # Remove _py suffix: agents_base_py -> agents_base
            clean = name[:-3]
            import_names.add(clean)
            
            # If there are dots (from subdirectories), handle them separately
            if '.' in clean:
                # e.g., "subdir.agents_base" - split by dots first
                dot_parts = clean.split('.')
                processed_parts = []
                
                for part in dot_parts:
                    # Each part might have underscores that represent dots
                    if '_' in part:
                        # Try keeping as-is and also converting to dots
                        processed_parts.append([part, part.replace('_', '.')])
                    else:
                        processed_parts.append([part])
                
                # Generate combinations (but this could explode, so limit it)
                if len(processed_parts) <= 3:
                    # For now, just use the most likely combinations
                    import_names.add('.'.join(p[0] for p in processed_parts))
                    if any(len(p) > 1 for p in processed_parts):
                        import_names.add('.'.join(p[-1] for p in processed_parts))
            
            # Main transformation: underscores to dots
            # agents_base -> agents.base
            # services_battle_cache -> services.battle.cache
            parts = clean.split('_')
            
            if len(parts) >= 2:
                # Full dot notation
                import_names.add('.'.join(parts))
                
                # Common patterns based on your project structure
                # Pattern 1: First part is package, rest stay together
                # services_battle_cache -> services.battle_cache
                if len(parts) >= 3:
                    import_names.add(f"{parts[0]}.{'_'.join(parts[1:])}")
                    
                    # Pattern 2: First two parts are packages
                    # services_battle_cache -> services.battle.cache
                    import_names.add(f"{parts[0]}.{parts[1]}.{'_'.join(parts[2:])}")
                    
                # Pattern 3: Progressive dot conversion
                # services_battle_cache_manager ->
                # services.battle_cache_manager, services.battle.cache_manager
                for i in range(1, min(len(parts), 4)):  # Limit to avoid explosion
                    partial = '.'.join(parts[:i]) + '.' + '_'.join(parts[i:])
                    import_names.add(partial)
            
            # Special case for _init files (package imports)
            if '_init' in clean:
                # agents_init_py -> agents
                # services_battle_init_py -> services.battle
                module_name = clean.replace('_init', '')
                if module_name:
                    import_names.add(module_name)
                    # Also try with dots
                    parts = module_name.split('_')
                    if len(parts) > 1:
                        import_names.add('.'.join(parts))
        
        # Remove any empty or invalid entries
        import_names.discard('')
        import_names.discard('.')
        
        # Return as sorted list for consistency
        return sorted(list(import_names))
    
    def parse_file(self, filepath):
        """Parse a Python file and extract its dependencies."""
        try:
            rel_path = str(filepath.relative_to(self.root_dir))
        except ValueError:
            return
            
        # Normalize path
        rel_path = rel_path.replace('\\', '/')
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Update line count
            lines = content.splitlines()
            self.files[rel_path]['lines'] = len(lines)
            
            # Skip very large files that might cause AST parsing issues
            if len(content) > 1_000_000:  # 1MB
                if self.verbose:
                    print(f"  ⚠️  Skipping very large file: {rel_path}", file=sys.stderr)
                return
            
            # Parse AST
            try:
                tree = ast.parse(content, filename=str(filepath))
                self.extract_imports(tree, rel_path)
            except SyntaxError as e:
                if self.verbose:
                    print(f"  Syntax error in {rel_path} line {e.lineno}: {e.msg}", file=sys.stderr)
            except Exception as e:
                if self.verbose:
                    print(f"  Error parsing {rel_path}: {e}", file=sys.stderr)
                    
        except Exception as e:
            if self.verbose:
                print(f"  Error reading {rel_path}: {e}", file=sys.stderr)
    
    def extract_imports(self, tree, current_file):
        """Extract all imports from the AST."""
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # import module.name
                    for alias in node.names:
                        if alias.name:
                            self.process_import(alias.name, current_file)
                        
                elif isinstance(node, ast.ImportFrom):
                    # from module import name
                    module = node.module or ''
                    
                    if module.startswith('.'):
                        # Relative import - try to resolve
                        self.process_relative_import(module, current_file, node)
                    elif module:
                        # Absolute import
                        self.process_import(module, current_file)
                        
                        # Also check if "from module import name" where name is a submodule
                        # e.g., "from agents import base" where base is agents_base_py.py
                        if node.names:
                            for alias in node.names:
                                if alias.name and alias.name != '*':
                                    # Try module.name as a potential file import
                                    full_import = f"{module}.{alias.name}"
                                    self.process_import(full_import, current_file)
        except Exception as e:
            if self.verbose:
                print(f"  Error extracting imports from {current_file}: {e}", file=sys.stderr)
    
    def process_import(self, module_name, current_file):
        """Process an import statement and determine if it's internal or external."""
        if not module_name:
            return
            
        # Skip if importing itself
        if module_name == current_file or module_name == current_file.replace('/', '.'):
            return
            
        # Check if this import maps to a local file
        if module_name in self.import_to_file:
            target_file = self.import_to_file[module_name]
            if target_file != current_file:  # Don't count self-imports
                self.dependencies[current_file].add(target_file)
                self.imported_by[target_file].add(current_file)
                if self.verbose:
                    print(f"    {current_file} -> {target_file} (via '{module_name}')", file=sys.stderr)
        else:
            # External dependency - only track the top-level package
            top_level = module_name.split('.')[0]
            self.external_deps[current_file].add(top_level)
    
    def process_relative_import(self, module_name, current_file, node=None):
        """Handle relative imports like 'from . import x' or 'from ..module import y'."""
        # For now, just track that there's a relative import
        # This could be enhanced to resolve the actual target
        if self.verbose:
            import_items = []
            if node and hasattr(node, 'names'):
                import_items = [alias.name for alias in node.names if alias.name]
            items_str = ', '.join(import_items) if import_items else 'unknown'
            print(f"    {current_file} has relative import: {module_name} ({items_str})", file=sys.stderr)
    
    def find_clusters(self):
        """Find groups of files that depend on each other."""
        clusters = []
        visited = set()
        
        for file in self.files:
            if file in visited:
                continue
                
            # Build a cluster starting from this file using BFS
            cluster = set()
            to_explore = {file}  # Use set to avoid duplicates
            
            while to_explore:
                current = to_explore.pop()  # Note: set.pop() is arbitrary but that's OK here
                if current in cluster:
                    continue
                if current not in self.files:  # Skip invalid files
                    continue
                    
                cluster.add(current)
                visited.add(current)
                
                # Add files this one depends on
                for dep in self.dependencies.get(current, []):
                    if dep not in cluster and dep in self.files:
                        to_explore.add(dep)
                
                # Add files that depend on this one
                for dependent in self.imported_by.get(current, []):
                    if dependent not in cluster and dependent in self.files:
                        to_explore.add(dependent)
            
            if cluster:  # Only add non-empty clusters
                clusters.append(cluster)
        
        return clusters
    
    def find_circular_dependencies(self):
        """Detect circular import chains."""
        all_cycles = []
        
        def find_cycles(node, path, visited_in_path):
            """DFS to find cycles."""
            if node in visited_in_path:
                # Found a cycle - extract it from path
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                return [cycle]
            
            visited_in_path.add(node)
            cycles = []
            
            for dep in self.dependencies.get(node, []):
                if dep in self.files:  # Ensure dep is a valid file
                    cycles.extend(find_cycles(dep, path + [dep], visited_in_path.copy()))
            
            return cycles
        
        # Find all cycles starting from each file
        visited_starts = set()
        for file in self.files:
            if file not in visited_starts:
                visited_starts.add(file)
                cycles = find_cycles(file, [file], set())
                all_cycles.extend(cycles)
        
        # Deduplicate cycles
        seen = set()
        unique_cycles = []
        
        for cycle in all_cycles:
            if len(cycle) > 1:
                # Normalize cycle (smallest element first, then in order)
                min_elem = min(cycle)
                min_idx = cycle.index(min_elem)
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                
                if normalized not in seen:
                    seen.add(normalized)
                    unique_cycles.append(list(normalized))
        
        return unique_cycles
    
    def generate_report(self):
        """Generate the analysis report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DEPENDENCY ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary statistics
        total_files = len(self.files)
        total_deps = sum(len(deps) for deps in self.dependencies.values())
        total_lines = sum(f.get('lines', 0) for f in self.files.values())
        
        lines.append(f"SUMMARY")
        lines.append(f"  Files analyzed: {total_files}")
        lines.append(f"  Total lines of code: {total_lines:,}")
        lines.append(f"  Internal dependencies found: {total_deps}")
        lines.append(f"  Files with dependencies: {len(self.dependencies)}")
        lines.append(f"  Files imported by others: {len(self.imported_by)}")
        lines.append("")
        
        # Hub files (imported by many others)
        lines.append(" HUB FILES (Central to your codebase)")
        lines.append("-" * 40)
        hub_files = [(f, deps) for f, deps in self.imported_by.items() if len(deps) > 0]
        hub_files.sort(key=lambda x: len(x[1]), reverse=True)
        
        if hub_files:
            shown = 0
            for file, importers in hub_files:
                if len(importers) >= 2:  # Only show files imported by 2+ others
                    lines.append(f"  {file} ({self.files.get(file, {}).get('lines', 0)} lines)")
                    importer_list = sorted(list(importers))[:3]
                    lines.append(f"    Imported by {len(importers)} files: {', '.join(importer_list)}")
                    if len(importers) > 3:
                        lines.append(f"    ... and {len(importers)-3} more")
                    shown += 1
                    if shown >= 5:
                        break
            
            if shown == 0:
                lines.append("  No significant hub files (imported by 2+ files)")
        else:
            lines.append("  No hub files detected")
            lines.append("  This might indicate:")
            lines.append("  - Import detection issues (check -v output)")
            lines.append("  - Highly decoupled code (good!)")
            lines.append("  - Missing dependencies")
        lines.append("")
        
        # Circular dependencies
        lines.append("🔄 CIRCULAR DEPENDENCIES")
        lines.append("-" * 40)
        circular = self.find_circular_dependencies()
        if circular:
            for cycle in circular[:10]:  # Limit to 10 to avoid spam
                cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
                lines.append(f"  {cycle_str}")
            if len(circular) > 10:
                lines.append(f"  ... and {len(circular)-10} more cycles")
            lines.append("")
            lines.append("  ⚠️  These files MUST be refactored together!")
        else:
            lines.append("  None found ✓")
        lines.append("")
        
        # Isolated files
        lines.append("🏝️ ISOLATED FILES (Can be refactored independently)")
        lines.append("-" * 40)
        isolated = []
        for file in self.files:
            # File is isolated if it neither imports nor is imported
            has_deps = file in self.dependencies and len(self.dependencies[file]) > 0
            is_imported = file in self.imported_by and len(self.imported_by[file]) > 0
            if not has_deps and not is_imported:
                isolated.append(file)
        
        if isolated:
            # Sort by size
            isolated.sort(key=lambda f: self.files.get(f, {}).get('lines', 0), reverse=True)
            for file in isolated[:10]:
                file_lines = self.files.get(file, {}).get('lines', 0)
                lines.append(f"  {file} ({file_lines} lines)")
            if len(isolated) > 10:
                lines.append(f"  ... and {len(isolated)-10} more")
        else:
            lines.append("  No isolated files found")
        lines.append("")
        
        # File clusters
        lines.append("📦 FILE CLUSTERS (Groups that should be refactored together)")
        lines.append("-" * 40)
        clusters = self.find_clusters()
        
        # Sort clusters by total lines, but safely handle missing line counts
        def cluster_size(cluster):
            return sum(self.files.get(f, {}).get('lines', 0) for f in cluster)
        
        clusters = sorted(clusters, key=cluster_size, reverse=True)
        
        shown_clusters = 0
        for cluster in clusters:
            if len(cluster) < 2:  # Skip single-file clusters
                continue
                
            total_lines = cluster_size(cluster)
            shown_clusters += 1
            lines.append(f"\nCluster {shown_clusters}: {len(cluster)} files, {total_lines:,} lines")
            
            # Show files in cluster
            sorted_files = sorted(cluster, 
                                key=lambda f: self.files.get(f, {}).get('lines', 0), 
                                reverse=True)
            for file in sorted_files[:5]:
                deps_count = len(self.dependencies.get(file, []))
                imported_count = len(self.imported_by.get(file, []))
                file_lines = self.files.get(file, {}).get('lines', 0)
                lines.append(f"  - {file} ({file_lines} lines, {deps_count} deps, imported by {imported_count})")
            if len(cluster) > 5:
                lines.append(f"  ... and {len(cluster)-5} more files")
            
            # Recommend if this is a good refactoring group
            if total_lines < 2000 and len(cluster) <= 5:
                lines.append(f"   Good size for refactoring together")
            elif total_lines > 5000:
                lines.append(f"  ⚠️  Too large - consider breaking into smaller groups")
            else:
                lines.append(f"  ℹ️  Moderate size - review carefully before refactoring")
            
            shown_clusters += 1
            if shown_clusters >= 5:
                break
        
        if shown_clusters == 0:
            lines.append("\n  No multi-file clusters found")
        
        lines.append("")
        
        # Refactoring recommendations
        lines.append(" RECOMMENDED REFACTORING GROUPS")
        lines.append("-" * 40)
        recommendations = self.generate_recommendations(clusters)
        
        if recommendations:
            for i, rec in enumerate(recommendations[:5], 1):
                lines.append(f"\n{i}. {rec['title']} ({rec['total_lines']:,} lines)")
                lines.append(f"   Files to upload together:")
                for file in rec['files']:
                    file_lines = self.files.get(file, {}).get('lines', 0)
                    lines.append(f"   - {file} ({file_lines} lines)")
                lines.append(f"   Reason: {rec['reason']}")
        else:
            lines.append("\n  No clear refactoring groups identified")
            lines.append("  Consider grouping files by functional area")
        
        # Debug section if no dependencies found
        if total_deps == 0:
            lines.append("")
            lines.append("⚠️  WARNING: No internal dependencies detected!")
            lines.append("-" * 40)
            lines.append("Possible issues:")
            lines.append("1. Import statements don't match file naming pattern")
            lines.append("2. Files use only relative imports (partially supported)")
            lines.append("3. Files have no imports (unusual for a real project)")
            lines.append("")
            lines.append("Debugging tips:")
            lines.append("- Run with -v flag for detailed import analysis")
            lines.append("- Check that files use format: agents_base_py.py imported as 'agents.base'")
            lines.append("")
            
            # Show sample of external deps to help debug
            all_externals = set()
            for deps in self.external_deps.values():
                all_externals.update(deps)
            
            if all_externals:
                lines.append("External dependencies detected (top-level packages):")
                for dep in sorted(all_externals)[:15]:
                    lines.append(f"  - {dep}")
                if len(all_externals) > 15:
                    lines.append(f"  ... and {len(all_externals)-15} more")
        
        return "\n".join(lines)
    
    def generate_recommendations(self, clusters):
        """Generate specific refactoring recommendations."""
        recommendations = []
        
        # Process clusters
        for cluster in clusters:
            # Skip clusters with invalid files
            valid_files = [f for f in cluster if f in self.files and self.files[f].get('lines', 0) > 0]
            if not valid_files:
                continue
                
            total_lines = sum(self.files[f].get('lines', 0) for f in valid_files)
            
            # Small, self-contained clusters (ideal for refactoring)
            if 200 < total_lines < 2000 and 2 <= len(valid_files) <= 5:
                recommendations.append({
                    'files': sorted(valid_files),
                    'total_lines': total_lines,
                    'title': f'Small cluster ({len(valid_files)} files)',
                    'reason': 'Self-contained group, perfect size for refactoring'
                })
            
            # Medium clusters that might be manageable
            elif 2000 <= total_lines < 4000 and len(valid_files) <= 8:
                # Take first 5 files sorted by size
                sorted_files = sorted(valid_files, 
                                    key=lambda f: self.files[f].get('lines', 0), 
                                    reverse=True)
                selected_files = sorted_files[:min(5, len(sorted_files))]
                selected_lines = sum(self.files[f].get('lines', 0) for f in selected_files)
                
                recommendations.append({
                    'files': selected_files,
                    'total_lines': selected_lines,
                    'title': f'Medium cluster (subset of {len(valid_files)} files)',
                    'reason': 'Interconnected group, consider refactoring in phases'
                })
        
        # Add hub files with their immediate dependents
        hub_files = [(f, deps) for f, deps in self.imported_by.items() 
                    if len(deps) >= 2 and f in self.files]
        hub_files.sort(key=lambda x: len(x[1]), reverse=True)
        
        for file, all_importers in hub_files[:3]:  # Top 3 hub files
            # Take up to 3 dependents
            dependents = [d for d in list(all_importers)[:3] if d in self.files]
            if not dependents:
                continue
                
            group = [file] + dependents
            total_lines = sum(self.files[f].get('lines', 0) for f in group)
            
            if total_lines < 3000:
                recommendations.append({
                    'files': group,
                    'total_lines': total_lines,
                    'title': f'Hub file + key dependents',
                    'reason': f'{file} is central (imported by {len(all_importers)} files)'
                })
        
        # Add isolated files that are good candidates
        for file in self.files:
            if file not in self.dependencies and file not in self.imported_by:
                file_lines = self.files[file].get('lines', 0)
                if 100 < file_lines < 1000:
                    recommendations.append({
                        'files': [file],
                        'total_lines': file_lines,
                        'title': 'Isolated file',
                        'reason': 'No dependencies - can be safely refactored alone'
                    })
        
        # Sort by size (prefer smaller chunks that fit in context)
        recommendations.sort(key=lambda x: (x['total_lines'], len(x['files'])))
        
        # Deduplicate recommendations (same file set)
        seen_sets = set()
        unique_recs = []
        for rec in recommendations:
            file_set = frozenset(rec['files'])
            if file_set not in seen_sets:
                seen_sets.add(file_set)
                unique_recs.append(rec)
        
        return unique_recs[:10]  # Return top 10 recommendations


def main():
    # Check Python version
    if sys.version_info < (3, 6):
        print("Error: Python 3.6 or higher is required")
        sys.exit(1)
        
    parser = argparse.ArgumentParser(
        description="Analyze Python project dependencies for safe refactoring"
    )
    parser.add_argument(
        "path", 
        nargs="?", 
        default=".", 
        help="Path to analyze (default: current directory)"
    )
    parser.add_argument(
        "-v", 
        "--verbose", 
        action="store_true",
        help="Show detailed import analysis"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)
    
    try:
        analyzer = DependencyAnalyzer(args.path, verbose=args.verbose)
        report = analyzer.analyze()
        
        print(report)
        
        # Save to file
        output_file = "dependency_report.txt"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"\nReport saved to: {output_file}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not save report to file: {e}", file=sys.stderr)
            
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()#!/usr/bin/env python3
"""
Python Project Dependency Analyzer - Clean Rewrite
Designed for projects where flat files will become nested folders.
E.g., agents_base_py.py -> agents/base.py
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
import argparse


class DependencyAnalyzer:
    def __init__(self, root_dir=".", verbose=False):
        self.root_dir = Path(root_dir)
        self.verbose = verbose
        
        # Core data structures
        self.files = {}  # filename -> file info
        self.dependencies = defaultdict(set)  # file -> set of files it depends on
        self.imported_by = defaultdict(set)  # file -> set of files that import it
        self.external_deps = defaultdict(set)  # file -> external packages
        
        # Build mapping of how imports resolve to actual files
        self.import_to_file = {}  # "agents.base" -> "agents_base_py.py"
        self.file_to_imports = defaultdict(set)  # "agents_base_py.py" -> {"agents.base", "agents_base"}
        
    def analyze(self):
        """Main analysis pipeline."""
        print("Starting dependency analysis...")
        
        # Step 1: Discover all Python files
        py_files = self.discover_files()
        if not py_files:
            return "No Python files found!"
        
        print(f"Found {len(py_files)} Python files")
        
        # Step 2: Build import mappings
        self.build_import_mappings(py_files)
        
        # Step 3: Parse each file and extract dependencies
        for py_file in py_files:
            self.parse_file(py_file)
        
        # Step 4: Generate report
        return self.generate_report()
    
    def discover_files(self):
        """Find all Python files in the project."""
        py_files = []
        for path in self.root_dir.rglob("*.py"):
            # Skip virtual environments, cache, and the analyzer itself
            path_str = str(path)
            if any(skip in path_str for skip in ["venv/", "env/", "__pycache__", ".pyc", "dependency_analyzer.py"]):
                continue
            py_files.append(path)
        return py_files
    
    def build_import_mappings(self, py_files):
        """Build bidirectional mappings between import names and actual files.
        
        Key insight: agents_base_py.py is imported as "agents.base"
        """
        for py_file in py_files:
            rel_path = str(py_file.relative_to(self.root_dir))
            
            # Store file info
            self.files[rel_path] = {
                'path': py_file,
                'lines': 0  # Will be updated when parsing
            }
            
            # Generate all possible import names for this file
            import_names = self.generate_import_names(rel_path)
            
            for import_name in import_names:
                self.import_to_file[import_name] = rel_path
                self.file_to_imports[rel_path].add(import_name)
                
            if self.verbose and import_names:
                # Show only first few to avoid spam
                display_names = import_names[:3]
                names_str = ', '.join(display_names)
                if len(import_names) > 3:
                    names_str += f' (+ {len(import_names)-3} more)'
                print(f"  {rel_path} -> {names_str}")
    
    def generate_import_names(self, filepath):
        """Generate all possible ways this file might be imported.
        
        agents_base_py.py might be imported as:
        - agents.base
        - agents_base
        - from agents import base
        
        Also handles subdirectories:
        - subdir/module_py.py -> subdir.module
        """
        import_names = set()  # Use set to avoid duplicates
        
        # Remove .py extension
        name = filepath[:-3] if filepath.endswith('.py') else filepath
        
        # Handle subdirectories (convert / to .)
        name = name.replace('/', '.')
        name = name.replace(os.sep, '.')  # Handle Windows paths too
        
        # Always include exact name
        import_names.add(name)
        
        # If it ends with _py, that's our special pattern
        if name.endswith('_py'):
            # Remove _py suffix
            clean = name[:-3]
            import_names.add(clean)
            
            # Split by both dots and underscores to handle mixed patterns
            # This handles cases like subdir.agents_base -> subdir.agents.base
            parts = clean.replace('.', '_').split('_')
            
            # Add all possible dot combinations
            if len(parts) >= 2:
                # Full dot notation
                import_names.add('.'.join(parts))
                
                # First part could be package, rest could be module
                # services_battle_cache -> services.battle_cache
                import_names.add(f"{parts[0]}.{'_'.join(parts[1:])}")
                
                # For 3+ parts, try different combinations
                if len(parts) >= 3:
                    # services_battle_cache could be:
                    # - services.battle.cache (all dots)
                    # - services.battle_cache (partial dots)
                    for i in range(1, len(parts)):
                        partial = '.'.join(parts[:i]) + '.' + '_'.join(parts[i:])
                        import_names.add(partial)
            
            # Special case for _init files (package imports)
            if '_init' in clean:
                # agents_init_py -> agents (importing the package)
                # services_battle_init_py -> services.battle
                module_name = clean.replace('_init', '')
                if module_name:
                    import_names.add(module_name)
                    import_names.add(module_name.replace('_', '.'))
                    
                    # Also add partial dot notations for package imports
                    parts = module_name.split('_')
                    if len(parts) > 1:
                        import_names.add('.'.join(parts))
        
        # Remove any empty strings that might have been added
        import_names.discard('')
        
        return list(import_names)
    
    def parse_file(self, filepath):
        """Parse a Python file and extract its dependencies."""
        rel_path = str(filepath.relative_to(self.root_dir))
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Update line count
            self.files[rel_path]['lines'] = len(content.splitlines())
            
            # Parse AST
            try:
                tree = ast.parse(content)
                self.extract_imports(tree, rel_path)
            except SyntaxError as e:
                if self.verbose:
                    print(f"  Syntax error in {rel_path}: {e}")
                    
        except Exception as e:
            if self.verbose:
                print(f"  Error reading {rel_path}: {e}")
    
    def extract_imports(self, tree, current_file):
        """Extract all imports from the AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # import module.name
                for alias in node.names:
                    self.process_import(alias.name, current_file)
                    
            elif isinstance(node, ast.ImportFrom):
                # from module import name
                module = node.module or ''
                
                if module.startswith('.'):
                    # Relative import - try to resolve
                    self.process_relative_import(module, current_file)
                elif module:
                    # Absolute import
                    self.process_import(module, current_file)
                    
                    # Also check if "from module import name" where name is a submodule
                    # e.g., "from agents import base" where base is agents_base_py.py
                    if node.names:
                        for alias in node.names:
                            if alias.name and alias.name != '*':
                                # Try module.name as a potential file import
                                full_import = f"{module}.{alias.name}"
                                self.process_import(full_import, current_file)
    
    def process_import(self, module_name, current_file):
        """Process an import statement and determine if it's internal or external."""
        if not module_name:
            return
            
        # Check if this import maps to a local file
        if module_name in self.import_to_file:
            target_file = self.import_to_file[module_name]
            if target_file != current_file:  # Don't count self-imports
                self.dependencies[current_file].add(target_file)
                self.imported_by[target_file].add(current_file)
                if self.verbose:
                    print(f"    {current_file} imports {target_file} (via '{module_name}')")
        else:
            # External dependency
            self.external_deps[current_file].add(module_name)
    
    def process_relative_import(self, module_name, current_file):
        """Handle relative imports like 'from . import x' or 'from ..module import y'."""
        # For now, just track that there's a relative import
        # This could be enhanced to resolve the actual target
        if self.verbose:
            print(f"    {current_file} has relative import: {module_name}")
    
    def find_clusters(self):
        """Find groups of files that depend on each other."""
        clusters = []
        visited = set()
        
        for file in self.files:
            if file in visited:
                continue
                
            # Build a cluster starting from this file using BFS
            cluster = set()
            to_explore = {file}  # Use set to avoid duplicates
            
            while to_explore:
                current = to_explore.pop()
                if current in cluster:
                    continue
                    
                cluster.add(current)
                visited.add(current)
                
                # Add files this one depends on
                for dep in self.dependencies.get(current, []):
                    if dep not in cluster and dep in self.files:  # Ensure dep is valid
                        to_explore.add(dep)
                
                # Add files that depend on this one
                for dependent in self.imported_by.get(current, []):
                    if dependent not in cluster and dependent in self.files:  # Ensure valid
                        to_explore.add(dependent)
            
            clusters.append(cluster)
        
        return clusters
    
    def find_circular_dependencies(self):
        """Detect circular import chains."""
        circular = []
        visited_global = set()
        
        def find_cycles(node, path, rec_stack):
            """DFS to find cycles."""
            if node in rec_stack:
                # Found a cycle - extract it from path
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                return [cycle]
            
            if node in visited_global:
                return []
            
            visited_global.add(node)
            rec_stack.add(node)
            cycles = []
            
            for dep in self.dependencies.get(node, []):
                cycles.extend(find_cycles(dep, path + [dep], rec_stack.copy()))
            
            return cycles
        
        # Find all cycles
        all_cycles = []
        for file in self.files:
            if file not in visited_global:
                cycles = find_cycles(file, [file], set())
                all_cycles.extend(cycles)
        
        # Deduplicate cycles
        seen = set()
        for cycle in all_cycles:
            if len(cycle) > 1:
                # Normalize cycle (smallest element first)
                min_idx = cycle.index(min(cycle))
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                if normalized not in seen:
                    seen.add(normalized)
                    circular.append(list(normalized))
        
        return circular
    
    def generate_report(self):
        """Generate the analysis report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DEPENDENCY ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary statistics
        total_files = len(self.files)
        total_deps = sum(len(deps) for deps in self.dependencies.values())
        lines.append(f"SUMMARY")
        lines.append(f"  Files analyzed: {total_files}")
        lines.append(f"  Internal dependencies found: {total_deps}")
        lines.append(f"  Files with dependencies: {len(self.dependencies)}")
        lines.append(f"  Files imported by others: {len(self.imported_by)}")
        lines.append("")
        
        # Hub files (imported by many others)
        lines.append(" HUB FILES (Central to your codebase)")
        lines.append("-" * 40)
        hub_files = [(f, deps) for f, deps in self.imported_by.items() if len(deps) > 0]
        hub_files.sort(key=lambda x: len(x[1]), reverse=True)
        
        if hub_files:
            for file, importers in hub_files[:5]:
                lines.append(f"  {file}")
                importer_list = sorted(list(importers))[:3]
                lines.append(f"    Imported by {len(importers)} files: {', '.join(importer_list)}")
                if len(importers) > 3:
                    lines.append(f"    ... and {len(importers)-3} more")
        else:
            lines.append("  No hub files detected - unusual for a real project!")
            lines.append("  Check that imports are being detected correctly.")
        lines.append("")
        
        # Circular dependencies
        lines.append("🔄 CIRCULAR DEPENDENCIES")
        lines.append("-" * 40)
        circular = self.find_circular_dependencies()
        if circular:
            for cycle in circular:
                cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
                lines.append(f"  {cycle_str}")
            lines.append("")
            lines.append("  ⚠️  These files MUST be refactored together!")
        else:
            lines.append("  None found ✓")
        lines.append("")
        
        # Isolated files
        lines.append("🏝️ ISOLATED FILES (Can be refactored independently)")
        lines.append("-" * 40)
        isolated = []
        for file in self.files:
            if file not in self.dependencies and file not in self.imported_by:
                isolated.append(file)
        
        if isolated:
            for file in isolated[:10]:
                file_lines = self.files.get(file, {}).get('lines', 0)
                lines.append(f"  {file} ({file_lines} lines)")
            if len(isolated) > 10:
                lines.append(f"  ... and {len(isolated)-10} more")
        else:
            lines.append("  No isolated files found")
        lines.append("")
        
        # File clusters
        lines.append("📦 FILE CLUSTERS (Groups that should be refactored together)")
        lines.append("-" * 40)
        clusters = self.find_clusters()
        # Sort clusters by total lines, but safely handle missing line counts
        clusters = sorted(clusters, 
                         key=lambda c: sum(self.files.get(f, {}).get('lines', 0) for f in c), 
                         reverse=True)
        
        for i, cluster in enumerate(clusters[:5], 1):
            total_lines = sum(self.files.get(f, {}).get('lines', 0) for f in cluster)
            lines.append(f"\nCluster {i}: {len(cluster)} files, {total_lines} lines")
            
            # Show files in cluster
            for file in sorted(cluster)[:5]:
                deps_count = len(self.dependencies.get(file, []))
                imported_count = len(self.imported_by.get(file, []))
                file_lines = self.files.get(file, {}).get('lines', 0)
                lines.append(f"  - {file} ({file_lines} lines, {deps_count} deps, imported by {imported_count})")
            if len(cluster) > 5:
                lines.append(f"  ... and {len(cluster)-5} more files")
            
            # Recommend if this is a good refactoring group
            if total_lines < 2000 and len(cluster) <= 5:
                lines.append(f"  ✓ Good size for refactoring together")
            elif total_lines > 5000:
                lines.append(f"  ⚠️  Too large - consider breaking into smaller groups")
        
        lines.append("")
        
        # Refactoring recommendations
        lines.append(" RECOMMENDED REFACTORING GROUPS")
        lines.append("-" * 40)
        recommendations = self.generate_recommendations(clusters)
        for i, rec in enumerate(recommendations[:5], 1):
            lines.append(f"\n{i}. {rec['title']} ({rec['total_lines']} lines)")
            lines.append(f"   Files to upload together:")
            for file in rec['files']:
                lines.append(f"   - {file}")
            lines.append(f"   Reason: {rec['reason']}")
        
        # Debug section if no dependencies found
        if total_deps == 0:
            lines.append("")
            lines.append("⚠️  WARNING: No dependencies detected!")
            lines.append("-" * 40)
            lines.append("Possible issues:")
            lines.append("1. Import statements might not match file naming pattern")
            lines.append("2. Files might be using relative imports not yet handled")
            lines.append("3. Try running with -v flag for detailed output")
            
            # Show sample of external deps to help debug
            lines.append("\nSample external dependencies detected:")
            all_external = set()
            for deps in self.external_deps.values():
                all_external.update(deps)
            for dep in sorted(all_external)[:10]:
                lines.append(f"  - {dep}")
        
        return "\n".join(lines)
    
    def generate_recommendations(self, clusters):
        """Generate specific refactoring recommendations."""
        recommendations = []
        
        for cluster in clusters:
            # Skip clusters with invalid files
            valid_files = [f for f in cluster if f in self.files and self.files[f].get('lines', 0) > 0]
            if not valid_files:
                continue
                
            total_lines = sum(self.files[f].get('lines', 0) for f in valid_files)
            
            # Small, self-contained clusters
            if 200 < total_lines < 2000 and len(valid_files) <= 5:
                recommendations.append({
                    'files': sorted(valid_files),
                    'total_lines': total_lines,
                    'title': f'Small cluster ({len(valid_files)} files)',
                    'reason': 'Self-contained group, manageable size for refactoring'
                })
            
            # Single file refactoring
            elif len(valid_files) == 1 and total_lines < 1000:
                file = list(valid_files)[0]
                recommendations.append({
                    'files': [file],
                    'total_lines': total_lines,
                    'title': 'Single file refactor',
                    'reason': 'Isolated file with no dependencies'
                })
        
        # Add hub files with their immediate dependents
        for file in self.imported_by:
            if len(self.imported_by[file]) >= 3 and file in self.files:
                dependents = [d for d in list(self.imported_by[file])[:3] if d in self.files]
                if not dependents:
                    continue
                group = [file] + dependents
                total_lines = sum(self.files[f].get('lines', 0) for f in group)
                if total_lines < 3000:
                    recommendations.append({
                        'files': group,
                        'total_lines': total_lines,
                        'title': f'Hub file + dependents',
                        'reason': f'{file} is a central file imported by {len(self.imported_by[file])} others'
                    })
        
        # Sort by size (prefer smaller chunks)
        recommendations.sort(key=lambda x: x['total_lines'])
        return recommendations


def main():
    # Check Python version
    if sys.version_info < (3, 6):
        print("Error: Python 3.6 or higher is required")
        sys.exit(1)
        
    parser = argparse.ArgumentParser(
        description="Analyze Python project dependencies for safe refactoring"
    )
    parser.add_argument(
        "path", 
        nargs="?", 
        default=".", 
        help="Path to analyze (default: current directory)"
    )
    parser.add_argument(
        "-v", 
        "--verbose", 
        action="store_true",
        help="Show detailed import analysis"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist")
        sys.exit(1)
    
    analyzer = DependencyAnalyzer(args.path, verbose=args.verbose)
    report = analyzer.analyze()
    
    print(report)
    
    # Save to file
    output_file = "dependency_report.txt"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {output_file}")
    except Exception as e:
        print(f"Warning: Could not save report to file: {e}")


if __name__ == "__main__":
    main()