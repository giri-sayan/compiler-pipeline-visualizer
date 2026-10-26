"""
Flask API — Comprehensive Compiler Pipeline Visualizer Server (Review 3 Upgrade).

Wires together all 5 pipeline stages + pedagogical explainer + diff mode + safe execution:
  Stage 1: Lexer (Tokens)
  Stage 2: Parser (AST)
  Stage 3: Semantic Analyzer (Symbol Table & Scope Diagnostics)
  Stage 4: IR Generator (Three-Address Code & Quadruples)
  Stage 5: Target Code Generator (x86-64 & Educational Pseudo-Assembly)
  Execution: Safe Sandboxed Execution (TAC VM & Subprocess Engine)
  Diff Mode: Side-by-Side Multi-Stage Difference Engine
  Multi-Language: C, C++, Java, Python, JavaScript, Toy Mini-Lang
"""

import os
import re
from flask import Flask, request, jsonify, send_from_directory
from languages import get_compiler, LANGUAGE_SPECS
from languages.base import make_diagnostic
import diff_service

app = Flask(__name__, static_folder="static")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit for large document compilation & diff payloads

PRESETS = {
    # ========================== C PRESETS ==========================
    "c_complete": {
        "name": "C: Complete Program (#include & printf)",
        "language": "c",
        "category": "hello",
        "source": """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}"""
    },
    "c_precedence": {
        "name": "C: Precedence Demo ((2 + 3) * 4)",
        "language": "c",
        "category": "arithmetic",
        "source": """#include <stdio.h>

int main() {
    int x = 2 + 3 * 4;
    int y = (2 + 3) * 4;
    return 0;
}"""
    },
    "c_variables": {
        "name": "C: Typed Variables & Declarations",
        "language": "c",
        "category": "variables",
        "source": """#include <stdio.h>

int main() {
    int count = 10;
    float rate = 2.5;
    char letter = 'A';
    int total = count * 2;
    printf("Total = %d\\n", total);
    return 0;
}"""
    },
    "c_conditional": {
        "name": "C: Control Flow (if / else)",
        "language": "c",
        "category": "conditional",
        "source": """#include <stdio.h>

int main() {
    int score = 85;
    int bonus = 0;
    if (score > 80) {
        bonus = 10;
    } else {
        bonus = 2;
    }
    return 0;
}"""
    },
    "c_unsupported_loop": {
        "name": "C [Unsupported]: while Loop (Educational Diagnostic)",
        "language": "c",
        "category": "loop",
        "source": """#include <stdio.h>

int main() {
    int i = 0;
    while (i < 5) {
        i = i + 1;
    }
    return 0;
}"""
    },
    "c_function": {
        "name": "C: Functions & Parameter Passing",
        "language": "c",
        "category": "function",
        "source": """#include <stdio.h>

int multiply(int a, int b) {
    return a * b;
}

int main() {
    int x = 6;
    int y = 7;
    int product = multiply(x, y);
    printf("Product = %d\\n", product);
    return 0;
}"""
    },
    "c_semantic_error": {
        "name": "C [Error]: Typo 'rintf' Diagnostic",
        "language": "c",
        "category": "error",
        "source": """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    rintf("Result = %d\\n", total);
    return 0;
}"""
    },
    "c_lexical_error": {
        "name": "C [Error]: Unrecognized '@' Character",
        "language": "c",
        "category": "error",
        "source": """#include <stdio.h>

int main() {
    int total = 3 @ 4;
    return 0;
}"""
    },
    "c_syntax_error": {
        "name": "C [Error]: Missing Operand '3 + ;'",
        "language": "c",
        "category": "error",
        "source": """#include <stdio.h>

int main() {
    int total = 3 + ;
    return 0;
}"""
    },
    "c_semantic_warning": {
        "name": "C [Warning]: Uninitialized Var",
        "language": "c",
        "category": "warning",
        "source": """#include <stdio.h>

int main() {
    int a;
    int b = a + 5;
    return 0;
}"""
    },
    "c_large_benchmark": {
        "name": "C [Scale]: 500-Line Large Benchmark",
        "language": "c",
        "category": "scale",
        "source": """#include <stdio.h>

int main() {
    int acc = 0;
""" + "\n".join(f"    int v_{i} = {i} * 2 + 1;\n    acc = acc + v_{i};" for i in range(1, 248)) + """
    printf("Accumulated Total = %d\\n", acc);
    return 0;
}"""
    },

    # ========================== C++ PRESETS ==========================
    "cpp_complete": {
        "name": "C++: Stream I/O & Class Architecture",
        "language": "cpp",
        "category": "hello",
        "source": """#include <iostream>
using namespace std;

class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
};

int main() {
    Calculator calc;
    int a = 15;
    int b = 25;
    int total = calc.add(a, b);
    cout << "Calculated Sum: " << total << endl;
    return 0;
}"""
    },
    "cpp_arithmetic": {
        "name": "C++: Arithmetic & Operator Precedence",
        "language": "cpp",
        "category": "arithmetic",
        "source": """#include <iostream>
using namespace std;

int main() {
    int a = 12;
    int b = 8;
    int c = 4;
    int res1 = a + b * c;
    int res2 = (a + b) * c;
    cout << "Arithmetic: " << res1 << " vs " << res2 << endl;
    return 0;
}"""
    },
    "cpp_variables": {
        "name": "C++: Typed Variables & Declarations",
        "language": "cpp",
        "category": "variables",
        "source": """#include <iostream>
using namespace std;

int main() {
    int count = 42;
    double ratio = 3.14;
    char symbol = 'Z';
    bool isActive = true;
    cout << "Count: " << count << endl;
    return 0;
}"""
    },
    "cpp_conditional": {
        "name": "C++: Conditionals (if / else)",
        "language": "cpp",
        "category": "conditional",
        "source": """#include <iostream>
using namespace std;

int main() {
    int score = 88;
    if (score >= 90) {
        cout << "Grade: A" << endl;
    } else {
        cout << "Grade: B" << endl;
    }
    return 0;
}"""
    },
    "cpp_classes": {
        "name": "C++: Class Methods & Instantiation",
        "language": "cpp",
        "category": "function",
        "source": """#include <iostream>
using namespace std;

class Multiplier {
public:
    int compute(int x, int y) {
        return x * y;
    }
};

int main() {
    Multiplier mult;
    int result = mult.compute(6, 7);
    cout << "Computed: " << result << endl;
    return 0;
}"""
    },
    "cpp_error": {
        "name": "C++ [Error]: Typo 'coutt' & 'ednl' Suggestion",
        "language": "cpp",
        "category": "error",
        "source": """#include <iostream>
using namespace std;

int main() {
    int total = 42;
    coutt << "Value = " << total << ednl;
    return 0;
}"""
    },

    # ========================== JAVA PRESETS ==========================
    "java_complete": {
        "name": "Java: Standard Class & main Method",
        "language": "java",
        "category": "hello",
        "source": """public class Main {
    public static void main(String[] args) {
        int base = 10;
        int multiplier = 4;
        int total = base * multiplier + 2;
        System.out.println("Java Computed Result: " + total);
    }
}"""
    },
    "java_arithmetic": {
        "name": "Java: Arithmetic & Operator Precedence",
        "language": "java",
        "category": "arithmetic",
        "source": """public class Main {
    public static void main(String[] args) {
        int a = 15;
        int b = 6;
        int c = 3;
        int r1 = a + b * c;
        int r2 = (a + b) * c;
        System.out.println("Arithmetic: " + r1);
    }
}"""
    },
    "java_variables": {
        "name": "Java: Typed Variables & Declarations",
        "language": "java",
        "category": "variables",
        "source": """public class Main {
    public static void main(String[] args) {
        int count = 50;
        double rate = 4.75;
        boolean active = true;
        System.out.println("Java Count: " + count);
    }
}"""
    },
    "java_conditional": {
        "name": "Java: Control Flow (if / else)",
        "language": "java",
        "category": "conditional",
        "source": """public class Main {
    public static void main(String[] args) {
        int score = 85;
        if (score >= 80) {
            System.out.println("Grade: Honor");
        } else {
            System.out.println("Grade: Standard");
        }
    }
}"""
    },
    "java_methods": {
        "name": "Java: Class Methods & Invocations",
        "language": "java",
        "category": "function",
        "source": """public class Main {
    public int multiply(int a, int b) {
        return a * b;
    }

    public static void main(String[] args) {
        int x = 7;
        int y = 9;
        int total = x * y;
        System.out.println("Java Methods Total: " + total);
    }
}"""
    },
    "java_error": {
        "name": "Java [Error]: Typo 'prntln' Diagnostic",
        "language": "java",
        "category": "error",
        "source": """public class Main {
    public static void main(String[] args) {
        int x = 100;
        System.out.prntln("Value is: " + x);
    }
}"""
    },
    "java_missing_main": {
        "name": "Java [Error]: Missing 'main' Method",
        "language": "java",
        "category": "error",
        "source": """public class Main {
    public void start() {
        System.out.println("Hello");
    }
}"""
    },

    # ========================== PYTHON PRESETS ==========================
    "python_complete": {
        "name": "Python: Functions & Control Flow",
        "language": "python",
        "category": "hello",
        "source": """def calculate_grade(score):
    if score >= 90:
        return 100
    else:
        return score + 5

def main():
    initial_score = 82
    final_score = calculate_grade(initial_score)
    print("Final Score:", final_score)

main()"""
    },
    "python_arithmetic": {
        "name": "Python: Expressions & Precedence",
        "language": "python",
        "category": "arithmetic",
        "source": """def main():
    a = 14
    b = 6
    c = 2
    r1 = a + b * c
    r2 = (a + b) * c
    print("Precedence:", r1, "vs", r2)

main()"""
    },
    "python_variables": {
        "name": "Python: Dynamic Variables & Assignments",
        "language": "python",
        "category": "variables",
        "source": """def main():
    name = "Compiler"
    items = 42
    ratio = 3.14159
    is_ready = True
    print("Variables:", name, items, ratio)

main()"""
    },
    "python_conditional": {
        "name": "Python: Control Flow (if / elif / else)",
        "language": "python",
        "category": "conditional",
        "source": """def evaluate(val):
    if val > 50:
        return val * 2
    else:
        return val + 10

def main():
    res = evaluate(25)
    print("Result:", res)

main()"""
    },
    "python_loops": {
        "name": "Python: Loops (while Loop Accumulation)",
        "language": "python",
        "category": "loop",
        "source": """def main():
    total = 0
    i = 1
    while i <= 5:
        total = total + i
        i = i + 1
    print("Accumulated Sum:", total)

main()"""
    },
    "python_functions": {
        "name": "Python: Function Definitions & Calls",
        "language": "python",
        "category": "function",
        "source": """def multiply(x, y):
    return x * y

def main():
    product = multiply(8, 7)
    print("Product:", product)

main()"""
    },
    "python_error": {
        "name": "Python [Error]: Typo 'pirnt' Diagnostic",
        "language": "python",
        "category": "error",
        "source": """def main():
    total = 3 + 4 * 2
    pirnt("Result =", total)

main()"""
    },

    # ========================== JAVASCRIPT PRESETS ==========================
    "js_complete": {
        "name": "JavaScript: ES6 Functions & Console",
        "language": "js",
        "category": "hello",
        "source": """function computeBonus(base, factor) {
    let result = base * factor + 10;
    return result;
}

let baseSalary = 50;
let bonusFactor = 2;
let total = computeBonus(baseSalary, bonusFactor);
console.log("Total Compensation:", total);"""
    },
    "js_arithmetic": {
        "name": "JavaScript: Arithmetic & Strict Precedence",
        "language": "js",
        "category": "arithmetic",
        "source": """let a = 18;
let b = 6;
let c = 2;
let r1 = a + b * c;
let r2 = (a + b) * c;
console.log("Arithmetic:", r1, "vs", r2);"""
    },
    "js_variables": {
        "name": "JavaScript: let & const Declarations",
        "language": "js",
        "category": "variables",
        "source": """let count = 30;
const multiplier = 3;
let isActive = true;
let total = count * multiplier;
console.log("JS Total:", total);"""
    },
    "js_conditional": {
        "name": "JavaScript: Control Flow (if / else)",
        "language": "js",
        "category": "conditional",
        "source": """let score = 78;
if (score >= 70) {
    console.log("Status: Passed");
} else {
    console.log("Status: Needs Improvement");
}"""
    },
    "js_functions": {
        "name": "JavaScript: Functions & Computations",
        "language": "js",
        "category": "function",
        "source": """function multiply(a, b) {
    let result = a * b;
    return result;
}

let x = 8;
let y = 6;
let total = multiply(x, y);
console.log("JS Multiplied:", total);"""
    },
    "js_error": {
        "name": "JavaScript [Error]: Typo 'conosle' Diagnostic",
        "language": "js",
        "category": "error",
        "source": """let total = 42;
conosle.log("Computed total:", total);"""
    },

    # ========================== TOY MINI-LANG PRESETS ==========================
    "toy_pipeline": {
        "name": "Toy: Assignments & Expressions",
        "language": "toy",
        "category": "hello",
        "source": """x = 5
y = x + 2
z = (x + y) * 3"""
    },
    "toy_arithmetic": {
        "name": "Toy: Arithmetic & Operator Precedence",
        "language": "toy",
        "category": "arithmetic",
        "source": """a = 10 + 4 * 2
b = (10 + 4) * 2
c = a + b"""
    },
    "toy_variables": {
        "name": "Toy: Multi-Variable Pipeline",
        "language": "toy",
        "category": "variables",
        "source": """base = 20
height = 10
area = (base * height) / 2"""
    },
    "toy_error": {
        "name": "Toy [Error]: Missing Operand in Expression",
        "language": "toy",
        "category": "error",
        "source": """x = 5 +
y = 10"""
    },
}


@app.route("/compile", methods=["POST"])
def compile_source():
    data = request.get_json(silent=True)
    if data is None and request.data:
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "error": "Invalid JSON request payload.",
            "diagnostics": [{
                "stage": "Source",
                "message": "Malformed JSON in request body.",
                "line": 1,
                "col": 1,
                "severity": "error"
            }],
            "stages": {
                "source": "failed",
                "tokens": "blocked",
                "ast": "blocked",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            }
        }), 400

    if data is None:
        data = {}

    source = data.get("source", "")
    language = data.get("language", "c")

    norm_lang = str(language).lower().strip() if language else "c"
    if norm_lang not in ("c", "cpp", "c++", "java", "python", "py", "js", "javascript", "toy"):
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "error": f"Unsupported language '{language}'. Supported languages: C, C++, Java, Python, JavaScript, Toy Lang.",
            "diagnostics": [{
                "stage": "Source",
                "message": f"Language '{language}' is not supported.",
                "line": 1,
                "col": 1,
                "severity": "error"
            }],
            "stages": {
                "source": "failed",
                "tokens": "blocked",
                "ast": "blocked",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            }
        }), 400

    try:
        compiler = get_compiler(norm_lang)
        result = compiler.compile(source)
        status_code = result.pop("status_code", 200)
        return jsonify(result), status_code
    except Exception as exc:
        app.logger.error("Unhandled compiler error during compilation for lang '%s': %s", language, exc, exc_info=True)
        diag = make_diagnostic("Pipeline", exc)
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "error": f"Internal compiler error: {type(exc).__name__}. Please check server logs.",
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "failed",
                "ast": "blocked",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            }
        }), 500


@app.route("/diff", methods=["POST"])
def diff_programs():
    data = request.get_json(silent=True) or {}
    source_a = data.get("source_a", "")
    source_b = data.get("source_b", "")
    language = data.get("language", "c")

    if not source_a.strip() or not source_b.strip():
        return jsonify({"error": "Both Program A and Program B sources are required"}), 400

    try:
        comparison = diff_service.compare_programs(source_a, source_b, language=language)
        return jsonify({"success": True, "data": comparison})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/presets", methods=["GET"])
def get_presets():
    return jsonify(PRESETS)


@app.route("/languages", methods=["GET"])
def get_languages():
    return jsonify(LANGUAGE_SPECS)


@app.route("/")
def home():
    static_html = os.path.join(app.root_path, "static", "index.html")
    if os.path.exists(static_html):
        return app.send_static_file("index.html")
    return send_from_directory(app.root_path, "index.html")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5000)
