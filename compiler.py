# compiler.py
from lark import Lark, Tree
from db import mock_db, schema

# --- Phase 1 & 2: Parser ---
def get_parser():
    with open("grammar.lark", "r") as f:
        return Lark(f.read(), parser='lalr')

# --- Phase 3: Semantic Analysis ---
def semantic_analysis(tree: Tree):
    # Check if table exists
    sources = list(tree.find_data('single_table')) + list(tree.find_data('join_tables'))
    table_names = []
    for src in sources:
        t1 = str(src.children[0])
        if t1 not in schema: raise ValueError(f"Semantic Error: Table '{t1}' does not exist.")
        table_names.append(t1)
        
        if src.data == 'join_tables':
            t2 = str(src.children[1])
            if t2 not in schema: raise ValueError(f"Semantic Error: Table '{t2}' does not exist.")
            table_names.append(t2)

    # Check if WHERE columns exist
    available_columns = [col for table in table_names for col in schema[table]]
    for cond in tree.find_data('condition'):
        col = str(cond.children[0])
        if col not in available_columns:
            raise ValueError(f"Semantic Error: Column '{col}' in WHERE clause does not exist.")
    
    print("Semantic Analysis: Passed ✅")

# --- Phase 4: Intermediate Representation ---
class PlanNode:
    def execute(self): pass

class ScanNode(PlanNode):
    def __init__(self, table): self.table = table
    def execute(self): return mock_db[self.table]
    def __repr__(self): return f"Scan({self.table})"

class JoinNode(PlanNode):
    def __init__(self, left_child, right_child, left_col, right_col):
        self.left_child, self.right_child = left_child, right_child
        self.left_col, self.right_col = left_col, right_col
    def execute(self):
        # Nested Loop Join
        left_data = self.left_child.execute()
        right_data = self.right_child.execute()
        result = []
        for l_row in left_data:
            for r_row in right_data:
                if l_row.get(self.left_col) == r_row.get(self.right_col):
                    merged = {**l_row, **r_row}
                    result.append(merged)
        return result
    def __repr__(self): return f"Join({self.left_col}={self.right_col}) -> [{self.left_child}, {self.right_child}]"

class FilterNode(PlanNode):
    def __init__(self, col, op, val, child):
        self.col, self.op, self.val, self.child = col, op, val, child
    def execute(self):
        data = self.child.execute()
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
    def execute(self):
        data = self.child.execute()
        if not self.columns: return data
        return [{k: row[k] for k in self.columns if k in row} for row in data]
    def __repr__(self): return f"Project({', '.join(self.columns) if self.columns else '*'}) -> {self.child}"

def build_logical_plan(tree: Tree):
    # 1. Handle FROM / JOIN
    source_nodes = list(tree.find_data('single_table'))
    if source_nodes:
        plan = ScanNode(str(source_nodes[0].children[0]))
    else:
        join_nodes = list(tree.find_data('join_tables'))[0]
        t1, t2 = str(join_nodes.children[0]), str(join_nodes.children[1])
        c1, c2 = str(join_nodes.children[2]), str(join_nodes.children[3])
        plan = JoinNode(ScanNode(t1), ScanNode(t2), c1, c2)

    # 2. Handle WHERE
    for cond in tree.find_data('condition'):
        val = cond.children[2].children[0]
        val = val[1:-1] if val.startswith('"') or val.startswith("'") else float(val)
        plan = FilterNode(str(cond.children[0]), cond.children[1].data, val, plan)

    # 3. Handle SELECT
    col_list_node = list(tree.find_data('columns'))
    columns = [str(c) for c in col_list_node[0].children if c != ','] if col_list_node else []
    plan = ProjectNode(columns, plan)

    return plan

# --- Phase 5: Query Optimizer ---
def optimize_plan(plan: PlanNode):
    """
    Rule: Selection Push-down
    If we see Project -> Filter -> Join, move the Filter below the Join.
    """
    # Look for the exact pattern: Project -> Filter -> Join
    if (isinstance(plan, ProjectNode) and 
        isinstance(plan.child, FilterNode) and 
        isinstance(plan.child.child, JoinNode)):
        
        proj_node = plan
        filter_node = proj_node.child
        join_node = filter_node.child
        
        # Figure out which table the filter column belongs to
        filter_col = filter_node.col
        left_table = join_node.left_child.table
        right_table = join_node.right_child.table
        
        print(f"🔧 Optimizer Triggered: Moving Filter('{filter_col}') below the Join...")
        
        if filter_col in schema[left_table]:
            # Disconnect filter from join, attach it to the left table (users)
            filter_node.child = join_node.left_child
            join_node.left_child = filter_node
        elif filter_col in schema[right_table]:
            # Attach it to the right table (departments)
            filter_node.child = join_node.right_child
            join_node.right_child = filter_node
            
        # Re-link the Project node directly to the Join node
        proj_node.child = join_node
        return proj_node
        
    return plan

# --- Main Execution ---
if __name__ == "__main__":
    parser = get_parser()
    
    sql = 'SELECT name, dept_name FROM users JOIN departments ON dept_id = dept_id WHERE age > 20'
    print(f"Executing: {sql}\n")
    
    ast = parser.parse(sql)
    semantic_analysis(ast)
    
    logical_plan = build_logical_plan(ast)
    print("\n--- 1. Logical Query Plan (Unoptimized) ---")
    print(logical_plan)
    
    print("\n--- 2. Optimization Phase ---")
    optimized_plan = optimize_plan(logical_plan)
    print("Optimized Plan:")
    print(optimized_plan)
    
    print("\n--- 3. Execution Result ---")
    result = optimized_plan.execute()
    for row in result:
        print(row)