import streamlit as st
import streamlit.components.v1 as components
import json
from lark import Lark, Tree
from lark.exceptions import UnexpectedInput, UnexpectedToken

# --- 1. Grammar ---
GRAMMAR = """
?start: query
query: "SELECT"i column_list "FROM"i source ["WHERE"i condition]
column_list: (CNAME ("," CNAME)*) -> columns | "*" -> all_columns
source: CNAME -> single_table | CNAME "JOIN"i CNAME "ON"i CNAME "=" CNAME -> join_tables
condition: CNAME operator value
operator: "=" -> eq | ">" -> gt | "<" -> lt
value: SIGNED_NUMBER | ESCAPED_STRING
%import common.CNAME
%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
"""

@st.cache_resource
def get_parser():
    return Lark(GRAMMAR, parser='lalr')

# --- 2. Compiler Nodes & Engine ---
class PlanNode:
    def execute(self, db): pass

class ScanNode(PlanNode):
    def __init__(self, table): self.table = table
    def execute(self, db): return db[self.table]
    def __repr__(self): return f"Scan({self.table})"

class JoinNode(PlanNode):
    def __init__(self, left, right, l_col, r_col):
        self.left, self.right, self.l_col, self.r_col = left, right, l_col, r_col
    def execute(self, db):
        left_data = self.left.execute(db)
        right_data = self.right.execute(db)
        result = []
        for l_row in left_data:
            for r_row in right_data:
                if l_row.get(self.l_col) == r_row.get(self.r_col):
                    result.append({**l_row, **r_row})
        return result
    def __repr__(self): return f"Join({self.l_col}={self.r_col}) -> [{self.left}, {self.right}]"

class FilterNode(PlanNode):
    def __init__(self, col, op, val, child):
        self.col, self.op, self.val, self.child = col, op, val, child
    def execute(self, db):
        data = self.child.execute(db)
        filtered = []
        for row in data:
            row_val = row.get(self.col)
            if self.op == 'eq' and row_val == self.val: filtered.append(row)
            elif self.op == 'gt' and float(row_val) > self.val: filtered.append(row)
            elif self.op == 'lt' and float(row_val) < self.val: filtered.append(row)
        return filtered
    def __repr__(self): return f"Filter({self.col} {self.op} {self.val}) -> {self.child}"

class ProjectNode(PlanNode):
    def __init__(self, columns, child):
        self.columns, self.child = columns, child
    def execute(self, db):
        data = self.child.execute(db)
        if not self.columns: return data
        return [{k: row[k] for k in self.columns if k in row} for row in data]
    def __repr__(self): return f"Project({', '.join(self.columns) if self.columns else '*'}) -> {self.child}"

def semantic_analysis(tree: Tree, schema: dict):
    sources = list(tree.find_data('single_table')) + list(tree.find_data('join_tables'))
    table_names = []
    for src in sources:
        t1 = str(src.children[0])
        if t1 not in schema: raise ValueError(f"Table '{t1}' does not exist.")
        table_names.append(t1)
        if src.data == 'join_tables':
            t2 = str(src.children[1])
            if t2 not in schema: raise ValueError(f"Table '{t2}' does not exist.")
            table_names.append(t2)

    available_columns = [col for table in table_names for col in schema[table]]
    for cond in tree.find_data('condition'):
        col = str(cond.children[0])
        if col not in available_columns:
            raise ValueError(f"Column '{col}' in WHERE clause does not exist.")

def build_logical_plan(tree: Tree):
    source_nodes = list(tree.find_data('single_table'))
    if source_nodes:
        plan = ScanNode(str(source_nodes[0].children[0]))
    else:
        join_nodes = list(tree.find_data('join_tables'))[0]
        plan = JoinNode(ScanNode(str(join_nodes.children[0])), ScanNode(str(join_nodes.children[1])), 
                        str(join_nodes.children[2]), str(join_nodes.children[3]))

    for cond in tree.find_data('condition'):
        val = cond.children[2].children[0]
        val = val[1:-1] if val.startswith('"') or val.startswith("'") else float(val)
        plan = FilterNode(str(cond.children[0]), cond.children[1].data, val, plan)

    col_list_node = list(tree.find_data('columns'))
    columns = [str(c) for c in col_list_node[0].children if c != ','] if col_list_node else []
    return ProjectNode(columns, plan)

def optimize_plan(plan: PlanNode, schema: dict):
    if (isinstance(plan, ProjectNode) and isinstance(plan.child, FilterNode) and isinstance(plan.child.child, JoinNode)):
        proj, filter_node, join_node = plan, plan.child, plan.child.child
        col = filter_node.col
        if col in schema.get(join_node.left.table, []):
            filter_node.child, join_node.left = join_node.left, filter_node
        elif col in schema.get(join_node.right.table, []):
            filter_node.child, join_node.right = join_node.right, filter_node
        proj.child = join_node
    return plan

# --- 3. Robust AST Visualizer (Mermaid JS) ---
def render_mermaid_ast(tree):
    """Converts AST into Mermaid diagram syntax and injects it into the browser"""
    lines = ['graph TD']
    lines.append('classDef struct fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#0369a1;')
    lines.append('classDef leaf fill:#fef3c7,stroke:#b45309,stroke-width:2px,color:#b45309;')
    
    node_count = 0
    
    def traverse(node, parent_id=None):
        nonlocal node_count
        current_id = f'node_{node_count}'
        node_count += 1
        
        if isinstance(node, Tree):
            label = str(node.data)
            lines.append(f'{current_id}["{label}"]:::struct')
            if parent_id:
                lines.append(f'{parent_id} --> {current_id}')
            for child in node.children:
                traverse(child, current_id)
        else:
            label = str(node).replace('"', '&quot;')
            lines.append(f'{current_id}["{label}"]:::leaf')
            if parent_id:
                lines.append(f'{parent_id} --> {current_id}')
                
    traverse(tree)
    mermaid_code = '\n'.join(lines)
    
    # Inject JavaScript library directly into the UI safely
    components.html(f"""
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <div class="mermaid" style="display: flex; justify-content: center; margin-top: 20px;">
            {mermaid_code}
        </div>
    """, height=500, scrolling=True)


# --- 4. Streamlit UI/UX ---
st.set_page_config(page_title="SQL Compiler Studio", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("SQL Compiler Studio")
st.markdown("A visual parser, planner, and execution engine for relational queries.")

default_db = {
    "users": [
        {"id": 1, "name": "Alice", "age": 25, "dept_id": 101},
        {"id": 2, "name": "Bob", "age": 19, "dept_id": 102},
        {"id": 3, "name": "Charlie", "age": 30, "dept_id": 101}
    ],
    "departments": [
        {"dept_id": 101, "dept_name": "Engineering"},
        {"dept_id": 102, "dept_name": "Marketing"}
    ]
}
default_schema = {
    "users": ["id", "name", "age", "dept_id"],
    "departments": ["dept_id", "dept_name"]
}

# Sidebar for Configuration
with st.sidebar:
    st.header("Database Configuration")
    st.markdown("Modify the JSON below to add custom tables, columns, or rows.")
    db_input = st.text_area("Mock Database (JSON)", value=json.dumps(default_db, indent=2), height=300)
    schema_input = st.text_area("Table Schema (JSON)", value=json.dumps(default_schema, indent=2), height=200)

# Main Area for Querying (Auto-executes on change)
sql = st.text_input("Enter SQL Query (Auto-compiles as you type)", value='SELECT name, dept_name FROM users JOIN departments ON dept_id = dept_id WHERE age > 20')

# Live Compiler Execution
try:
    db_data = json.loads(db_input)
    schema_data = json.loads(schema_input)
    parser = get_parser()
    
    ast = parser.parse(sql)
    semantic_analysis(ast, schema_data)
    
    st.success("Compilation Successful: Query passed syntax and semantic validation.")
    
    tab1, tab2, tab3 = st.tabs(["Abstract Syntax Tree", "Execution Plans", "Result Set"])
    
    with tab1:
        st.markdown("### Visual Syntax Tree")
        st.markdown("The Lexer and Parser breakdown of your query statement.")
        # Renders beautiful Mermaid graph, no system installations required!
        render_mermaid_ast(ast)
        
    with tab2:
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("### Logical Plan")
            st.markdown("Unoptimized relational algebra.")
            logical_plan = build_logical_plan(ast)
            st.code(str(logical_plan), language="text")
        
        with col_right:
            st.markdown("### Physical Plan")
            st.markdown("Optimized via selection push-down.")
            optimized_plan = optimize_plan(logical_plan, schema_data)
            st.code(str(optimized_plan), language="text")
        
    with tab3:
        st.markdown("### Output Data")
        result = optimized_plan.execute(db_data)
        if result:
            st.dataframe(result, use_container_width=True)
        else:
            st.info("Query executed successfully, but returned zero rows.")

# Clean Error Handling
except UnexpectedToken as e:
    st.error(f"Syntax Error: Unexpected token at line {e.line}, column {e.column}")
    st.warning("Suggestion: Check the spelling of SQL keywords, ensure strings are properly quoted, and verify commas.")
except UnexpectedInput as e:
    st.error("Syntax Error: Query format was not recognized.")
    st.warning("Suggestion: Ensure your query follows the core structure: SELECT ... FROM ... [JOIN ... ON ...] [WHERE ...].")
except ValueError as e:
    st.error(f"Semantic Error: {str(e)}")
    st.warning("Suggestion: Verify that the tables and columns referenced in your query exactly match the schema provided in the sidebar.")
except json.JSONDecodeError:
    st.error("Configuration Error: Failed to parse Database or Schema. Please ensure they are valid JSON.")
except Exception as e:
    st.error(f"Execution Error: {str(e)}")