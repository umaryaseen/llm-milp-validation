"""Serialize source declarations like upstream utils.format_typed_mention (no tokenizer)."""

from typing import Any
from xml.sax.saxutils import escape

_TYPES = {
    "upperbound": "[UPPER_BOUND]",
    "lowerbound": "[LOWER_BOUND]",
    "sum": "[SUM_CONSTRAINT]",
    "linear": "[LINEAR_CONSTRAINT]",
    "ratio": "[RATIO_CONSTRAINT]",
    "xby": "[XBY_CONSTRAINT]",
    "xy": "[XY_CONSTRAINT]",
}


def tag(name: str, value: object) -> str:
    return f"<{name}>{escape(str(value).strip(' '))}</{name}>"


def declaration_xml(declaration: dict[str, Any]) -> str:
    kind = declaration["type"]
    parts: list[str] = []
    if kind in {"objective", "objvar"}:
        for field, label in [("direction", "OBJ_DIR"), ("name", "OBJ_NAME")]:
            if field in declaration and declaration[field] is not None:
                parts.append(tag(label, declaration[field]))
        for name, value in declaration.get("terms", {}).items():
            parts.extend([tag("VAR", name), tag("PARAM", value)])
        for name in declaration.get("vars", []):
            parts.extend([tag("VAR", name), tag("PARAM", "1")])
    else:
        for field, label in [
            ("direction", "CONST_DIR"),
            ("operator", "OPERATOR"),
            ("limit", "LIMIT"),
        ]:
            if field in declaration:
                parts.append(tag(label, declaration[field]))
        parts.append(tag("CONST_TYPE", _TYPES[kind]))
        if kind in {"upperbound", "lowerbound", "ratio"} and "var" in declaration:
            parts.append(tag("VAR", declaration["var"]))
        elif kind == "linear":
            for name, value in declaration["terms"].items():
                parts.extend([tag("VAR", name), tag("PARAM", value)])
        elif kind == "xby":
            if "y_var" in declaration and "param" in declaration:
                parts.extend([tag("VAR", declaration["y_var"]), tag("PARAM", declaration["param"])])
            if "x_var" in declaration:
                parts.append(tag("VAR", declaration["x_var"]))
        elif kind == "xy":
            for field in ["y_var", "x_var"]:
                if field in declaration:
                    parts.append(tag("VAR", declaration[field]))
    return "<DECLARATION>" + "".join(parts) + "</DECLARATION>"


def record_xml(record: dict[str, Any]) -> str:
    return "".join(
        declaration_xml(d) for d in [record["obj_declaration"], *record["const_declarations"]]
    )
