mock_db = {
    "users": [
        {"id": 1, "name": "Alice", "age": 25, "city": "Pune", "dept_id": 101},
        {"id": 2, "name": "Bob", "age": 19, "city": "Mumbai", "dept_id": 102},
        {"id": 3, "name": "Charlie", "age": 30, "city": "Pune", "dept_id": 101}
    ],
    "departments": [
        {"dept_id": 101, "dept_name": "Engineering"},
        {"dept_id": 102, "dept_name": "Marketing"}
    ]
}

# The Compiler uses this to validate queries before execution
schema = {
    "users": ["id", "name", "age", "city", "dept_id"],
    "departments": ["dept_id", "dept_name"]
}