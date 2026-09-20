"""Check JinjaX components the way the HTML templates are checked.

``hook.run_check`` reads ``TemplateResponse(...)`` call sites and ``.html``
templates. The frontend here is JinjaX instead, so this module reads
``catalog.render("Name", ...)`` call sites in the view modules and checks each
component against them:

* the component exists (E930);
* every keyword is a declared prop (E931);
* every required prop is passed (E932);
* the props are typed from the call site and the component is walked, so a
  misspelled attribute inside ``{{ character.titl }}`` is reported like any
  other template (E101/E110 from the shared walker).

Props passed between components (``<editorial.Quick :entry="entry" />``) are
typed only when the receiving ``{#def#}`` annotates them; an unannotated prop
stays unknown, which is the honest answer.
"""

from __future__ import annotations

import ast
import importlib
import re
from dataclasses import dataclass
from pathlib import Path

from .diagnostics import Diagnostic
from .discovery import ModuleIndex, RouteBinding, index_module
from .resolver import ResolutionError, Resolver
from .typerefs import UNKNOWN, OpaqueRef
from .walker import TemplateChecker

# JinjaX injects these into every component. ``__prefix`` is the internal
# variable its ``{% call %}`` blocks use for the caller's slot.
JINJAX_NAMES = ("content", "attrs", "catalog", "__prefix")
# Names accepted by ``catalog.render`` that are not declared props.
RESERVED = ("_content", "_attrs", "_html")

DEF_DIRECTIVE = re.compile(r"\{#def(.*?)#\}", re.DOTALL)
COMPONENT = re.compile(r"<([A-Za-z_][A-Za-z0-9_.]*)")


@dataclass
class JinjaxCall:
    """One ``catalog.render("Name", ...)`` call site."""

    module: ModuleIndex
    func: ast.FunctionDef | ast.AsyncFunctionDef
    lineno: int
    name: str
    kwargs: dict[str, ast.expr]


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside brackets, braces or quotes."""
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current: list[str] = []
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def declared_props(source: str) -> dict[str, bool]:
    """Prop name -> has a default, from the ``{#def ... #}`` header."""
    match = DEF_DIRECTIVE.search(source)
    if match is None:
        return {}
    props: dict[str, bool] = {}
    for part in _split_top_level(match.group(1)):
        text = part.strip()
        if not text:
            continue
        name = re.split(r"[:=]", text, maxsplit=1)[0].strip()
        if name.isidentifier():
            props[name] = "=" in text
    return props


def find_calls(view_paths: list[Path], source_root: Path) -> list[JinjaxCall]:
    """Every ``catalog.render("Literal", **kwargs)`` call site."""
    calls: list[JinjaxCall] = []
    for path in sorted(view_paths):
        try:
            module = index_module(path, source_root)
        except SyntaxError, UnicodeDecodeError:
            continue
        for func in module.functions.values():
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                callee = node.func
                if not isinstance(callee, ast.Attribute) or callee.attr != "render":
                    continue
                if not node.args:
                    continue
                first = node.args[0]
                if not isinstance(first, ast.Constant) or not isinstance(
                    first.value, str
                ):
                    continue
                calls.append(
                    JinjaxCall(
                        module=module,
                        func=func,
                        lineno=node.lineno,
                        name=first.value,
                        kwargs={kw.arg: kw.value for kw in node.keywords if kw.arg},
                    )
                )
    return calls


def _component_path(components_dir: Path, dotted: str) -> Path:
    return components_dir.joinpath(*dotted.split(".")).with_suffix(".jinja")


def run_jinjax_check(
    components_dir: Path,
    source_root: Path,
    views_glob: str,
    repo_root: Path,
    env_factory: str,
) -> tuple[list[Diagnostic], list[str]]:
    """Return (diagnostics, warnings) for every component call site."""
    module_name, _, attr = env_factory.partition(":")
    factory = getattr(importlib.import_module(module_name), attr)
    env = factory(str(components_dir)).jinja_env

    view_paths = [
        path
        for path in sorted(repo_root.glob(views_glob))
        if "testdata" not in path.parts
    ]
    resolver = Resolver()
    diagnostics: list[Diagnostic] = []
    warnings: list[str] = []

    for call in find_calls(view_paths, source_root):
        component = _component_path(components_dir, call.name)
        call_site = call.module.path.resolve().relative_to(repo_root.resolve())
        if not component.is_file():
            diagnostics.append(
                Diagnostic(
                    code="E930",
                    template=call_site.as_posix(),
                    lineno=call.lineno,
                    message=f"catalog.render('{call.name}') has no component",
                )
            )
            continue

        source = component.read_text(encoding="utf-8")
        template = component.resolve().relative_to(repo_root.resolve()).as_posix()
        props = declared_props(source)

        for keyword in call.kwargs:
            if keyword in props or keyword in RESERVED:
                continue
            diagnostics.append(
                Diagnostic(
                    code="E931",
                    template=template,
                    lineno=1,
                    message=f"<{call.name}> has no prop '{keyword}'",
                    detail=f"called from {call_site}:{call.lineno}",
                )
            )
        for prop, has_default in props.items():
            if not has_default and prop not in call.kwargs:
                diagnostics.append(
                    Diagnostic(
                        code="E932",
                        template=template,
                        lineno=1,
                        message=f"<{call.name}> requires prop '{prop}'",
                        detail=f"called from {call_site}:{call.lineno}",
                    )
                )

        binding = RouteBinding(
            module=call.module,
            func=call.func,
            lineno=call.lineno,
            templates=(call.name,),
            context=call.kwargs,
        )
        try:
            context, unresolved = resolver.resolve_binding(binding, None)
        except ResolutionError as exc:
            # The view module could not be imported: the props are still checked,
            # only their types are not.
            context, unresolved = {}, [f"{call_site}: {exc}"]
        warnings.extend(unresolved)
        # A prop with a default that this call site does not pass is still bound
        # inside the component, just untyped.
        for prop in props:
            context.setdefault(prop, UNKNOWN)
        for name in JINJAX_NAMES:
            context.setdefault(name, UNKNOWN)
        # A prop passed as None at one call site (a create form) is guarded by
        # `{% if character %}` inside the component, which this checker does not
        # model: treat it as unknown rather than reporting a false E103.
        for name, ref in list(context.items()):
            if isinstance(ref, OpaqueRef) and ref.py_type is type(None):
                context[name] = UNKNOWN

        checker = TemplateChecker(env, binding_label=f"{call_site}:{call.lineno}")
        checker.add_template(template, source)
        diagnostics.extend(checker.check(template, context).diagnostics)

    unique: dict[tuple, Diagnostic] = {}
    for diag in diagnostics:
        unique.setdefault((diag.code, diag.template, diag.lineno, diag.message), diag)
    ordered = sorted(unique.values(), key=lambda d: (d.template, d.lineno, d.code))
    return ordered, warnings
