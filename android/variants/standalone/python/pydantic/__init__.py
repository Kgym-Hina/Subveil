"""Minimal stand-in for the parts of pydantic v2 that pyatv uses.

pydantic v2 depends on pydantic-core, a Rust extension that is not available for
Android, so the standalone app ships this pure-Python subset instead.
"""

import copy
import enum
import typing

__all__ = ["BaseModel", "Field", "field_validator"]
VERSION = "2.0.0-subveil"

_MISSING = object()


class FieldInfo:
    def __init__(self, default=_MISSING, default_factory=None, annotation=None):
        self.default = default
        self.default_factory = default_factory
        self.annotation = annotation

    def get_default(self):
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is _MISSING:
            return _MISSING
        return copy.copy(self.default)


def Field(default=_MISSING, *, default_factory=None, **_):  # noqa: N802
    return FieldInfo(default, default_factory)


def field_validator(*fields, mode="after", **_):
    def decorator(func):
        target = func.__func__ if isinstance(func, (classmethod, staticmethod)) else func
        target.__subveil_validator__ = (fields, mode)
        return func

    return decorator


def _coerce(annotation, value):
    if value is None:
        return None
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        for arg in typing.get_args(annotation):
            if arg is type(None):
                continue
            try:
                return _coerce(arg, value)
            except (TypeError, ValueError):
                continue
        return value
    if origin in (list, typing.List):
        (item,) = typing.get_args(annotation) or (typing.Any,)
        return [_coerce(item, v) for v in value]
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel) and isinstance(value, dict):
            return annotation(**value)
        if issubclass(annotation, enum.Enum) and not isinstance(value, annotation):
            return annotation(value)
        if annotation is int and isinstance(value, str):
            return int(value)
        if annotation is float and isinstance(value, (str, int)):
            return float(value)
    return value


class BaseModel:
    model_fields: typing.Dict[str, FieldInfo] = {}
    _validators: typing.List[tuple] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        hints = typing.get_type_hints(cls)
        fields = {}
        for name, annotation in hints.items():
            if name.startswith("_") or name == "model_fields":
                continue
            default = cls.__dict__.get(name, _MISSING)
            if default is _MISSING:
                for base in cls.__mro__[1:]:
                    base_field = getattr(base, "model_fields", {}).get(name)
                    if base_field is not None:
                        default = FieldInfo(base_field.default, base_field.default_factory)
                        break
            info = default if isinstance(default, FieldInfo) else FieldInfo(default)
            info.annotation = annotation
            fields[name] = info
        cls.model_fields = fields
        validators = []
        for klass in reversed(cls.__mro__):
            for attr in vars(klass).values():
                func = attr.__func__ if isinstance(attr, (classmethod, staticmethod)) else attr
                spec = getattr(func, "__subveil_validator__", None)
                if spec is not None:
                    validators.append((spec[0], spec[1], func))
        cls._validators = validators

    def __init__(self, **data):
        values = {}
        for name, info in self.model_fields.items():
            if name in data:
                value = data[name]
            else:
                value = info.get_default()
                if value is _MISSING:
                    raise ValueError(f"{type(self).__name__}.{name} is required")
            values[name] = self._validate(name, value)
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @classmethod
    def _validate(cls, name, value):
        for fields, mode, func in cls._validators:
            if name in fields and mode == "before":
                value = func(cls, value)
        value = _coerce(cls.model_fields[name].annotation, value)
        for fields, mode, func in cls._validators:
            if name in fields and mode != "before":
                value = func(cls, value)
        return value

    @classmethod
    def model_validate(cls, data):
        if isinstance(data, cls):
            return data
        return cls(**data)

    def model_copy(self, *, update=None, deep=False):
        clone = copy.deepcopy(self) if deep else copy.copy(self)
        for name, value in (update or {}).items():
            if name in self.model_fields:
                object.__setattr__(clone, name, value)
        return clone

    def model_dump(self, *, exclude_defaults=False, **_):
        out = {}
        for name, info in self.model_fields.items():
            value = getattr(self, name)
            if isinstance(value, BaseModel):
                dumped = value.model_dump(exclude_defaults=exclude_defaults)
                if exclude_defaults and not dumped:
                    continue
                out[name] = dumped
                continue
            if isinstance(value, list):
                value = [v.model_dump(exclude_defaults=exclude_defaults)
                         if isinstance(v, BaseModel) else v for v in value]
            elif exclude_defaults and info.default_factory is None and value == info.default:
                continue
            if isinstance(value, enum.Enum):
                value = value.value
            out[name] = value
        return out

    def __iter__(self):
        for name in self.model_fields:
            yield name, getattr(self, name)

    def __eq__(self, other):
        return type(self) is type(other) and dict(self) == dict(other)

    def __repr__(self):
        args = ", ".join(f"{k}={v!r}" for k, v in self)
        return f"{type(self).__name__}({args})"
