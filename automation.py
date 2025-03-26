import os
import re
import subprocess
import sys
from pathlib import Path
# import json
import readline
import glob
import unicodedata

def slugify(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    return text

def read_markdown(file_path: str) -> str:
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f" Markdown file not found: {path}")
    return path.read_text(encoding='utf-8')

def complete_path(text, state):
    return (glob.glob(text + '*') + [None])[state]

def prompt_for_markdown_file() -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete_path)

    try:
        file_path = input("Enter markdown file path: ").strip()
        if not file_path:
            print("\033[31m Please provide a markdown file path.\033[0m")
            sys.exit(1)
        return file_path
    except KeyboardInterrupt:
        print("\n\033[33m User interrupted input.\033[0m")
        sys.exit(1)


def extract_project_id(markdown: str):
    match = re.search(r'<ReactProject\s+id="([^"]+)"\s*>', markdown)
    if not match:
        print("\033[31m <ReactProject id=\"...\"> tag not found. Please wrap your markdown with this tag.\033[0m")
        sys.exit(1)
    return match.group(1)

def run_command(command: str):
    print(f" Running command: {command}")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        raise RuntimeError(f" Command failed: {command} (Exit code: {result.returncode})")


def setup_shadcn(usingToast: bool):
    using_pnpm = False
    shadcn = "shadcn" if usingToast else "shadcn@latest"
    default_options = "" if usingToast else "-t next -b neutral --cwd ."


    if using_pnpm:
        try:
            run_command("npm i pnpm")
            run_command("pnpm --version")
            print("\033[32m pnpm is installed.\033[0m")
        except Exception:
            print("\033[33m pnpm installation failed. Falling back to npm.\033[0m")
            using_pnpm = False

    try:
        cmd = f"pnpm dlx {shadcn} init {default_options}" if using_pnpm \
              else f"npx {shadcn} init {default_options}"
        run_command(f"echo \".\" | {cmd}")

        add_cmd = f"pnpm dlx {shadcn} add -a" if using_pnpm else f"npx {shadcn} add -a"
        run_command(add_cmd)

        print("\033[32m ShadCN setup complete.\033[0m")
    except Exception as e:
        print("\033[31m Failed to initialize ShadCN:", str(e), "\033[0m")
        raise


def extract_files_from_markdown(content: str):
    pattern = r'```[a-zA-Z0-9]+\s+file="([^"]*)"\n([\s\S]*?)```'
    results = re.findall(pattern, content)

    for file, _ in results:
        if not file.strip():
            print("\033[31m Missing file name in one of the code blocks: file=\"\"\033[0m")
            sys.exit(1)

    return results

ignore_dependencies = []
blacklist_prefixes = ("next/")

def install_third_party_dependencies(files):
    dependencies = set()

    for file_name, code in files:
        matches = re.findall(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', code)
        for dep in matches:
            if dep in ignore_dependencies:
                continue
            if any(dep.startswith(prefix) for prefix in blacklist_prefixes):
                continue
            if not dep.startswith("./") and not dep.startswith("@/"):
                if "/" in dep: # Handle scenerios like "@hookform/resolvers/zod"
                    parts = dep.split("/")
                    scope = parts[0]
                    name = parts[1] if len(parts) > 1 else ""
                    dependencies.add(f"{scope}/{name}")
                else:
                    dependencies.add(dep)

    if dependencies:
        deps_string = " ".join(dependencies)
        print(f"\033[36m Detected dependencies: {deps_string}\033[0m")
        install_cmd = f"pnpm install {deps_string}" if Path("pnpm-lock.yaml").exists() else f"npm install {deps_string}"
        run_command(install_cmd)
    else:
        print(" No external dependencies to install.")


def write_project_files(files):
    for file_path, code in files:
        full_path = Path(file_path).resolve()
        if not full_path.parent.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)
            print(f" Created directory: {full_path.parent}")
        full_path.write_text(code, encoding='utf-8')
        print(f"\033[32m Created file: {full_path}\033[0m")


def reinstall_npm_package(package_name: str, package_json_data: dict):
    deps = package_json_data.get("dependencies", {})
    dev_deps = package_json_data.get("devDependencies", {})
    found = package_name in deps or package_name in dev_deps

    if not found:
        print(f"\033[33m {package_name} not found in package.json. Skipping reinstall.\033[0m")
        return

    uninstall_cmd = f"pnpm remove {package_name}" if Path("pnpm-lock.yaml").exists() else f"npm uninstall {package_name}"
    install_cmd = f"pnpm add {package_name}" if Path("pnpm-lock.yaml").exists() else f"npm install {package_name}"

    print(f" Reinstalling package: {package_name}")
    run_command(uninstall_cmd)
    run_command(install_cmd)
    print(f"\033[32m Reinstalled {package_name} successfully.\033[0m")

def process_markdown_project():
    markdown_file = prompt_for_markdown_file()
    print(f" Reading markdown file: {markdown_file}")
    content = read_markdown(markdown_file)

    file_name = Path(markdown_file).stem
    project_slug = slugify(file_name)
    print(f" Using project slug as folder name: {project_slug}")

    project_root = Path(project_slug).resolve()
    if project_root.exists():
        print(f"\033[31m Project directory already exists: {project_root}\033[0m")
        sys.exit(1)

    project_root.mkdir(parents=True)
    print(f"\033[32m Created project folder: {project_root}\033[0m")

    # find out if content has an import like this "@/components/ui/toast" or "@/components/ui/toaster"

    usingToast = False

    if "@/components/ui/toast" in content or "@/components/ui/toaster" in content:
        usingToast = True

    if usingToast:
        print("\033[32m Toast is enabled.\033[0m")
        run_command("npm install shadcn@v2.3.0")

    os.chdir(project_root)
    print(f" Changed working directory to: {project_root}")

    setup_shadcn(usingToast)

    project_files = extract_files_from_markdown(content)
    write_project_files(project_files)

    install_third_party_dependencies(project_files)


if __name__ == "__main__":
    try:
        process_markdown_project()

        # pkg_path = Path("package.json")
        # if pkg_path.exists():
        #     with pkg_path.open("r", encoding="utf-8") as f:
        #         pkg_data = json.load(f)
        #     reinstall_npm_package("zod", pkg_data)
        # else:
        #     print("\033[33m package.json not found. Skipping reinstall step.\033[0m")

        print("\033[32m All setup complete. Launching dev server...\033[0m")
        run_command("npm run dev")

    except KeyboardInterrupt:
        print("\n\033[33m Process interrupted by user.\033[0m")
        sys.exit(1)
    except Exception as err:
        print(f"\033[31m Unexpected exception:\033[0m {err}")
        sys.exit(1)
