"""
Language Compiler Registry & Pipeline Dispatcher.

Provides a unified interface across all supported languages:
  - C (Subset: #include, main, types, printf, conditionals)
  - C++ (Subset: <iostream>, using namespace std, cout <<, cin >>, classes, methods)
  - Java (Subset: public class Main, public static void main, System.out.println, types)
  - Python (Subset: def, print, control flow, arithmetic, standard ast parsing)
  - JavaScript (Subset: let, const, function, console.log, control flow)
  - Toy Mini-Lang (Legacy simple assignments and expressions)
"""

from typing import Dict, Any, Optional

SUPPORTED_LANGUAGES = {
    "c": "C",
    "cpp": "C++",
    "java": "Java",
    "python": "Python",
    "js": "JavaScript",
    "toy": "Toy Mini-Lang",
}

LANGUAGE_SPECS = {
    "c": {
        "name": "C (C99 Educational Subset)",
        "extension": ".c",
        "description": "Supports #include directives, function definitions (int main()), variable declarations, assignments, arithmetic/relational operators, if/else control flow, return statements, and stdio functions (printf, scanf).",
        "features": [
            "#include <stdio.h>, <stdlib.h>, <math.h>, <string.h>",
            "int main() entry point with parameter validation",
            "Typed variable declarations: int, float, double, char, void",
            "Binary and unary arithmetic with standard operator precedence",
            "Relational comparisons: ==, !=, <, >, <=, >=",
            "Control flow: if, if-else with block scoping",
            "Function calls with arguments: printf(\"Result = %d\\n\", total)",
            "Return statements with value checking",
            "Single-line (//) and multi-line (/* */) comments"
        ],
        "limitations": [
            "Pointers and pointer arithmetic are not yet modeled in AST",
            "Structs and typedefs are simplified to primitive type descriptors",
            "Loops (while, for) are planned for next release; if-else is fully supported"
        ]
    },
    "cpp": {
        "name": "C++ (Modern C++ Educational Subset)",
        "extension": ".cpp",
        "description": "Supports #include <iostream>, using namespace std, stream I/O (cout <<, cin >>, endl), classes with public/private access specifiers, member methods, constructors, object instantiation, and int main().",
        "features": [
            "#include <iostream>, <vector>, <string>, <cmath>",
            "using namespace std;",
            "Stream output: cout << \"Text\" << x << endl;",
            "Stream input: cin >> var;",
            "Classes: class Name { public: ... private: ... };",
            "Member functions and constructors",
            "Object declarations: Rectangle r;",
            "References (int& ref = x;) and auto type deduction",
            "int main() entry point validation"
        ],
        "limitations": [
            "Template metaprogramming is not supported",
            "Operator overloading beyond << and >> is not supported",
            "Multiple inheritance is simplified to single-class structures"
        ]
    },
    "java": {
        "name": "Java (Java 8+ Standard Subset)",
        "extension": ".java",
        "description": "Supports public class declarations, public static void main(String[] args) entry points, System.out.println, System.out.print, primitive types (int, double, boolean), String literals, class methods, and control flow.",
        "features": [
            "Class declarations: public class Main { ... }",
            "Required entry point: public static void main(String[] args)",
            "Standard console I/O: System.out.println(...) and System.out.print(...)",
            "Typed variable declarations: int, double, float, boolean, String",
            "Class fields and member methods",
            "Control flow: if, if-else, return",
            "Arithmetic, comparisons, and string concatenation"
        ],
        "limitations": [
            "Packages and imports are parsed but not resolved from filesystem",
            "Generics and interfaces are simplified to class descriptors",
            "Exception handling (try/catch) is planned for future release"
        ]
    },
    "python": {
        "name": "Python (Python 3.x Subset)",
        "extension": ".py",
        "description": "Uses Python's standard compiler AST and tokenizer. Supports function definitions (def), return statements, if/elif/else control flow, while/for loops, print(...) calls, variable assignments, and standard builtins.",
        "features": [
            "Genuine Python 3 AST parser (using Python standard library ast module)",
            "Functions: def function_name(args): ... return val",
            "Console I/O: print(\"Result =\", val)",
            "Dynamic variable assignments without static type keywords (x = 10)",
            "Full control flow: if, elif, else, while, for",
            "Arithmetic precedence and nested expressions",
            "Built-in function validation with typo suggestions (e.g. pirnt -> print)",
            "Undeclared/unassigned variable detection (NameError diagnostics)"
        ],
        "limitations": [
            "Async/await and generators are not converted to TAC",
            "Decorator syntax is recorded in AST but flattened in IR"
        ]
    },
    "js": {
        "name": "JavaScript (ES6+ Subset)",
        "extension": ".js",
        "description": "Supports let, const, var declarations, function definitions, console.log(...) output, if/else branching, while loops, return statements, and dynamic expressions.",
        "features": [
            "Variable declarations: let, const, var",
            "Functions: function name(args) { ... }",
            "Console I/O: console.log(\"Output:\", val)",
            "Control flow: if, else, while, return",
            "Arithmetic and strict/loose equality (===, !==, ==, !=)",
            "Typo suggestions for console (conosle -> console, etc.)"
        ],
        "limitations": [
            "DOM / Browser APIs (document, window) are not simulated",
            "Promises and async/await are not converted to linear TAC"
        ]
    },
    "toy": {
        "name": "Toy Mini-Lang",
        "extension": ".toy",
        "description": "Minimal pedagogical language for compiler construction fundamentals. Supports sequential variable assignments and arithmetic expressions.",
        "features": [
            "Sequential assignments: x = 5",
            "Expressions: y = x + 2 * 3",
            "Parentheses overriding precedence: z = (x + y) * 2"
        ],
        "limitations": [
            "No functions or control flow constructs"
        ]
    }
}


from languages.base import BaseCompiler
from languages.c_lang import CCompiler
from languages.cpp_lang import CPPCompiler
from languages.java_lang import JavaCompiler
from languages.python_lang import PythonCompiler
from languages.js_lang import JSCompiler
from languages.toy_lang import ToyCompiler

_COMPILERS: Dict[str, BaseCompiler] = {
    "c": CCompiler(),
    "cpp": CPPCompiler(),
    "c++": CPPCompiler(),
    "java": JavaCompiler(),
    "python": PythonCompiler(),
    "py": PythonCompiler(),
    "js": JSCompiler(),
    "javascript": JSCompiler(),
    "toy": ToyCompiler(),
}

def get_compiler(lang: Optional[str]) -> BaseCompiler:
    if not lang:
        return _COMPILERS["c"]
    norm = str(lang).lower().strip()
    return _COMPILERS.get(norm, _COMPILERS["c"])
