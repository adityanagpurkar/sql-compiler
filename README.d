# ⚙️ SQL Query Compiler & Optimizer

A mini-project demonstrating the core principles of Compiler Construction. Instead of compiling a procedural programming language into machine code, this project compiles a declarative language (SQL) into an optimized Intermediate Representation (Relational Algebra) and executes it against a mock JSON database.

It features a fully interactive web-based UI built with Streamlit, including a real-time visual Abstract Syntax Tree (AST) generated via Mermaid.js.

## ✨ Features

*   **Lexical & Syntax Analysis (Parser):** Validates SQL grammar using a Context-Free Grammar (CFG) defined in Lark.
*   **Semantic Analysis:** Verifies table existence and column bindings against a mock schema before execution.
*   **Logical Query Planning:** Converts the Abstract Syntax Tree (AST) into a tree of Relational Algebra nodes (Scan, Filter, Project, Join).
*   **Rule-Based Optimization (Selection Push-down):** Automatically optimizes the query plan by pushing `WHERE` filters below `JOIN` operations to minimize processed rows.
*   **Execution Engine:** A nested-loop execution engine that processes the optimized plan against a JSON database.
*   **Live Visual AST:** Generates a real-time, interactive node-graph of your parsed query using Mermaid.js.

## 🛠️ Tech Stack

*   **Python 3.x**: Core language
*   **Lark**: Parsing toolkit for Lexing and building the AST
*   **Streamlit**: Web framework for the interactive UI
*   **Mermaid.js**: Browser-based graph rendering for the AST visualizer

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/aditynagpurkar/sql-compiler.git](https://github.com/adityanagpurkar/sql-compiler.git)
   cd sql-compiler