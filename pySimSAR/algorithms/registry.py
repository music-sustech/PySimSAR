"""Generic algorithm registry for plugin-based extensibility."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class AlgorithmRegistry(Generic[T]):
    """Type-safe registry for algorithm plugins.

    Provides registration, lookup, and listing of algorithm implementations.
    Each registry instance manages a single algorithm type (e.g., waveforms,
    image formation algorithms).

    Parameters
    ----------
    base_class : type[T]
        The ABC that all registered algorithms must subclass.
    name : str
        Human-readable name for this registry (used in error messages).
    """

    def __init__(self, base_class: type[T], name: str) -> None:
        self._base_class = base_class
        self._name = name
        self._registry: dict[str, type[T]] = {}

    @property
    def name(self) -> str:
        return self._name

    def register(self, algorithm_class: type[T]) -> type[T]:
        """Register an algorithm class.

        Can be used as a decorator or called directly.

        Parameters
        ----------
        algorithm_class : type[T]
            The algorithm class to register. Must be a subclass of the
            registry's base class and must have a ``name`` attribute.

        Returns
        -------
        type[T]
            The registered class (unchanged), enabling decorator usage.

        Raises
        ------
        TypeError
            If algorithm_class is not a subclass of the base class.
        ValueError
            If an algorithm with the same name is already registered.
        """
        is_valid = isinstance(algorithm_class, type) and issubclass(
            algorithm_class, self._base_class
        )
        if not is_valid:
            raise TypeError(
                f"Cannot register {algorithm_class!r}: "
                f"must be a subclass of {self._base_class.__name__}"
            )

        if not hasattr(algorithm_class, "name"):
            raise TypeError(
                f"Cannot register {algorithm_class.__name__}: "
                f"must have a 'name' attribute"
            )

        algo_name = algorithm_class.name
        if callable(algo_name) and not isinstance(algo_name, property):
            raise TypeError(
                f"Cannot register {algorithm_class.__name__}: 'name' must be a "
                f"string attribute or property, not a method"
            )

        # For classes with property-based name, instantiation is needed to get
        # the name. We use a sentinel approach: check if it's a string on the class.
        if isinstance(algo_name, str):
            key = algo_name
        else:
            # name is likely a property — we can't resolve it without an instance.
            # Use the class name as fallback key.
            key = algorithm_class.__name__

        if key in self._registry:
            raise ValueError(
                f"Cannot register {algorithm_class.__name__}: "
                f"'{key}' is already registered in {self._name} registry"
            )

        self._registry[key] = algorithm_class
        return algorithm_class

    def get(self, name: str) -> type[T]:
        """Look up a registered algorithm class by name.

        Parameters
        ----------
        name : str
            The registered name of the algorithm.

        Returns
        -------
        type[T]
            The algorithm class.

        Raises
        ------
        KeyError
            If no algorithm is registered with the given name.
        """
        if name not in self._registry:
            available = ", ".join(sorted(self._registry.keys())) or "(none)"
            raise KeyError(
                f"Unknown {self._name} algorithm: '{name}'. "
                f"Available: {available}"
            )
        return self._registry[name]

    def list(self) -> list[str]:
        """Return sorted list of registered algorithm names."""
        return sorted(self._registry.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)

    def __repr__(self) -> str:
        return f"AlgorithmRegistry({self._name}, algorithms={self.list()})"
