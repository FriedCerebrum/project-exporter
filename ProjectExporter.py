import os
import base64
import tempfile
import sys
import codecs


def detect_encoding(file_path):
    """
    Detects the encoding of a file by checking for BOM (Byte Order Mark)
    and attempting various encodings.
    """
    # Check for BOM first
    encodings_to_check = [
        ('utf-8-sig', codecs.BOM_UTF8),
        ('utf-16-le', codecs.BOM_UTF16_LE),
        ('utf-16-be', codecs.BOM_UTF16_BE),
        ('utf-32-le', codecs.BOM_UTF32_LE),
        ('utf-32-be', codecs.BOM_UTF32_BE)
    ]

    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(4)
            for enc, bom in encodings_to_check:
                if raw_data.startswith(bom):
                    return enc
    except:
        pass

    # No BOM found or couldn't read file, try other encodings
    encodings = ['utf-8', 'latin1', 'cp1251', 'iso-8859-1', 'windows-1252']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)  # Try to read a small chunk
                return encoding
        except UnicodeDecodeError:
            continue
        except:
            pass

    # Default to utf-8 if we couldn't detect
    return 'utf-8'


def read_file_safely(file_path):
    """
    Reads a file with proper encoding detection.
    """
    encoding = detect_encoding(file_path)

    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        # If detected encoding fails, try with replacement
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                return f.read()
        except:
            pass
    except Exception:
        pass

    # Special handling for SQL files that might be UTF-16 encoded
    if file_path.lower().endswith('.sql'):
        try:
            # Special attempt for UTF-16
            with open(file_path, 'rb') as f:
                raw_data = f.read()

            # Try both UTF-16 encodings
            for enc in ['utf-16le', 'utf-16be']:
                try:
                    return raw_data.decode(enc)
                except:
                    continue
        except:
            pass

    # Last resort: try binary read and decode with replacement
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            for enc in ['utf-8', 'latin1', 'cp1251', 'utf-16le', 'utf-16be']:
                try:
                    return raw_data.decode(enc, errors='replace')
                except:
                    continue
    except:
        pass

    return None


def should_treat_as_text_by_extension(file_path):
    """
    Check if a file should be treated as text based on its extension.
    """
    text_extensions = {
        '.md', '.txt', '.sql', '.py', '.js', '.html', '.css', '.java', '.c', '.cpp', '.h',
        '.hpp', '.json', '.xml', '.yml', '.yaml', '.ini', '.cfg', '.conf', '.sh', '.bat',
        '.ps1', '.php', '.rb', '.pl', '.go', '.rs', '.ts', '.jsx', '.vue', '.csv'
    }

    _, ext = os.path.splitext(file_path.lower())
    return ext in text_extensions


def is_likely_binary_file(file_path):
    """
    Check if file is likely binary by extension first, then by content if needed.
    """
    # Check extension first
    if should_treat_as_text_by_extension(file_path):
        return False

    try:
        # Sample first few KB
        with open(file_path, 'rb') as f:
            sample = f.read(8192)

        if not sample:
            return False

        # Check for null bytes (common in binary files)
        if b'\x00' in sample:
            # Special case: UTF-16 encoded files have null bytes but are text
            if file_path.lower().endswith(('.sql', '.txt', '.md')):
                # Try to decode as UTF-16
                try:
                    sample.decode('utf-16le')
                    return False  # It decoded as UTF-16, so it's text
                except:
                    try:
                        sample.decode('utf-16be')
                        return False  # It decoded as UTF-16, so it's text
                    except:
                        pass  # Not UTF-16, continue checking

            # If we get here, it's likely binary
            return True

        # Count text vs. binary characters
        text_chars = set(bytes(range(32, 127)) + b'\n\r\t\f\b')
        binary_count = sum(1 for byte in sample if byte not in text_chars)

        # If >20% non-text chars, likely binary
        return binary_count / len(sample) > 0.2
    except:
        # In case of any error, assume it's not binary
        return False


def export_project_structure(root_dir, output_file, ignore_dirs=None, ignore_extensions=None):
    """
    Экспортирует структуру проекта и содержимое всех файлов в текстовый формат.

    Args:
        root_dir: Корневая директория проекта
        output_file: Путь к файлу для сохранения результата
        ignore_dirs: Список директорий для игнорирования (например, ['target', '.git'])
        ignore_extensions: Список расширений для игнорирования (например, ['.class', '.jar'])
    """
    if ignore_dirs is None:
        ignore_dirs = ['target', '.git', '.idea', 'node_modules', 'build', 'dist', 'ignore', '.vscode']

    if ignore_extensions is None:
        ignore_extensions = ['.class', '.jar', '.war', '.ear', '.zip', '.tar', '.gz', '.rar',
                             '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.pdf']

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Структура проекта: {os.path.basename(root_dir)}\n\n")
        f.write("```\n")

        # Записываем дерево директорий
        for root, dirs, files in os.walk(root_dir):
            # Фильтруем игнорируемые директории
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            level = root.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f"{indent}{os.path.basename(root)}/\n")

            sub_indent = ' ' * 4 * (level + 1)
            for file in sorted(files):
                if any(file.endswith(ext) for ext in ignore_extensions):
                    continue
                f.write(f"{sub_indent}{file}\n")

        f.write("```\n\n")

        # Записываем содержимое файлов
        f.write("# Содержимое файлов\n\n")

        files_exported = 0
        files_failed = 0

        for root, dirs, files in os.walk(root_dir):
            # Фильтруем игнорируемые директории
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file in sorted(files):
                if any(file.endswith(ext) for ext in ignore_extensions):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, root_dir)

                f.write(f"## {rel_path}\n\n")
                f.write("```\n")

                # Use our improved file reading function
                content = read_file_safely(file_path)

                if content is not None:
                    f.write(content)
                    files_exported += 1
                else:
                    f.write("[File reading error - content skipped]\n")
                    files_failed += 1

                f.write("```\n\n")

        # Добавляем информацию о base64 версии для больших проектов
        f.write(f"# Итоги экспорта\n\n")
        f.write(f"* Успешно экспортировано файлов: {files_exported}\n")
        f.write(f"* Не удалось экспортировать файлов: {files_failed}\n\n")

        f.write("# Base64 версия всего проекта\n\n")
        f.write("Если проект слишком большой, используйте эту base64-закодированную версию:\n\n")
        f.write("```\n")

        # Создаем временный файл со всем содержимым
        temp_path = tempfile.mktemp()

        # Рекурсивно записываем структуру с содержимым в более компактном формате
        with open(temp_path, 'w', encoding='utf-8') as temp:
            for root, dirs, files in os.walk(root_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]

                for file in files:
                    if any(file.endswith(ext) for ext in ignore_extensions):
                        continue

                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, root_dir)

                    temp.write(f"### FILE: {rel_path}\n")

                    # Use same improved file reading function
                    content = read_file_safely(file_path)

                    if content is not None:
                        temp.write(content)
                    else:
                        temp.write("[File reading error - content skipped]")

                    temp.write("\n\n")

        # Кодируем в base64
        try:
            with open(temp_path, 'rb') as temp:
                encoded = base64.b64encode(temp.read()).decode('utf-8')
                f.write(encoded)
        except Exception as e:
            f.write(f"[Error encoding project: {str(e)}]")

        # Удаляем временный файл
        try:
            os.unlink(temp_path)
        except:
            pass

        f.write("\n```")


# Пример использования
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python export_project.py <путь_к_проекту> [выходной_файл]")
        sys.exit(1)

    project_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "project_export.md"

    print(f"Экспорт проекта из {project_path} в {output_path}...")
    export_project_structure(project_path, output_path)
    print(f"Экспорт завершен! Результат сохранен в {output_path}")
