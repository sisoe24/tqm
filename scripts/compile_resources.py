"""Compile the resources for the application."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


def generate_qrc_file():
    print('Generating resources.qrc...')

    qrc_content = '<!DOCTYPE RCC>\n<RCC version="1.0">\n\n'

    # Add icons section
    icons = ROOT / 'resources' / 'icons' / 'dark'
    if icons.exists():
        qrc_content += '\t<qresource prefix="icons">\n'
        for svg_file in sorted(icons.glob('*.svg')):
            resources_folder = svg_file.parent.parent.parent
            relative_path = svg_file.relative_to(resources_folder)
            qrc_content += (
                f'\t\t<file alias="{icons.name}/{svg_file.stem}">{relative_path}</file>\n'
            )
        qrc_content += '\t</qresource>\n\n'

    # Add fonts section
    fonts_dir = ROOT / 'resources' / 'font'
    if fonts_dir.exists():
        qrc_content += '\t<qresource prefix="">\n'
        for font_file in sorted(fonts_dir.glob('*.ttf')):
            resources_folder = font_file.parent.parent
            relative_path = font_file.relative_to(resources_folder)
            qrc_content += f'\t\t<file>{relative_path}</file>\n'
        qrc_content += '\t</qresource>\n\n'

    qrc_content += '</RCC>\n'

    # Write the QRC file
    qrc_path = ROOT / 'resources' / 'resources.qrc'
    with open(qrc_path, 'w') as f:
        f.write(qrc_content)

    return qrc_path


def compile_resources():
    """Compile the resources."""
    print('Compiling resources...')

    # Generate the QRC file
    qrc_path = generate_qrc_file()

    # Compile the resource file
    output_path = ROOT / 'tqm' / '_resources_rc.py'

    # Run resource compiler
    subprocess.run([
        'poetry', 'run', 'pyside2-rcc',
        str(qrc_path), '-o',
        str(output_path)
    ], cwd=ROOT, check=True)

    print('Resources compiled successfully.')
    print(f'Output: {output_path}')


if __name__ == '__main__':
    compile_resources()
