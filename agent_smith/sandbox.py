import builtins
import importlib
from types import ModuleType


def _is_import_allowed(module_name, patterns):
    """Check exact module names and patterns ending in .*."""
    if module_name.startswith("."):
        return False

    for pattern in patterns:
        if module_name == pattern:
            return True

        if pattern.endswith(".*"):
            prefix = pattern[:-1]
            if module_name.startswith(prefix):
                return True

    return False


def _make_safe_import(authorized_imports):
    """Create an importer that checks the configured allowlist."""
    allowed_imports = tuple(authorized_imports)

    def restricted_import(
        name, globals=None, locals=None, fromlist=(), level=0
    ):
        if level != 0:
            raise ImportError("Relative imports are not allowed.")

        if not _is_import_allowed(name, allowed_imports):
            raise ImportError(f"Import not allowed: {name}")

        if fromlist:
            if "*" in fromlist:
                raise ImportError("Use explicit names instead of import *.")

            # Load the allowed module without processing fromlist yet.
            module = importlib.import_module(name)
            attributes = vars(module)

            for item in fromlist:
                value = attributes.get(item)

                if isinstance(value, ModuleType):
                    module_name = value.__name__
                elif item not in attributes:
                    module_name = f"{name}.{item}"
                else:
                    continue

                if not _is_import_allowed(module_name, allowed_imports):
                    raise ImportError(f"Import not allowed: {module_name}")

        return builtins.__import__(name, globals, locals, fromlist, level)

    return restricted_import