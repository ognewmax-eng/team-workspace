"""
Патч для исправления проблемы с importlib.metadata в Python 3.8.
Этот модуль должен импортироваться ПЕРЕД импортом Google API библиотек.
"""
import sys

def patch_importlib_metadata():
    """Патч для исправления проблемы с packages_distributions в Python 3.8."""
    try:
        import importlib.metadata
        # Проверяем наличие атрибута
        if not hasattr(importlib.metadata, 'packages_distributions'):
            # Пытаемся использовать importlib_metadata (отдельный пакет)
            try:
                import importlib_metadata
                # Копируем функцию из importlib_metadata в importlib.metadata
                if hasattr(importlib_metadata, 'packages_distributions'):
                    importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
                else:
                    # Создаем простую заглушку
                    def _packages_distributions():
                        return {}
                    importlib.metadata.packages_distributions = _packages_distributions
            except ImportError:
                # Если importlib_metadata не установлен, создаем заглушку
                def _packages_distributions():
                    return {}
                importlib.metadata.packages_distributions = _packages_distributions
    except (ImportError, AttributeError):
        # Если importlib.metadata не доступен, пытаемся создать заглушку
        try:
            import importlib_metadata
            # Создаем модуль-заглушку
            import importlib.metadata
            if not hasattr(importlib.metadata, 'packages_distributions'):
                if hasattr(importlib_metadata, 'packages_distributions'):
                    importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
                else:
                    importlib.metadata.packages_distributions = lambda: {}
        except:
            # Последняя попытка - создаем минимальную заглушку
            try:
                import importlib.metadata
                if not hasattr(importlib.metadata, 'packages_distributions'):
                    importlib.metadata.packages_distributions = lambda: {}
            except:
                pass

# Применяем патч при импорте модуля
patch_importlib_metadata()
