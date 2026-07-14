import os
import ast

def get_imported_modules(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return set()

def main():
    py_files = [f for f in os.listdir('.') if f.endswith('.py')]
    modules = set([f[:-3] for f in py_files])
    
    used_modules = set()
    for f in py_files:
        imports = get_imported_modules(f)
        used_modules.update(imports)
        
    unused = modules - used_modules
    
    print("Potentially Unused Local Modules (never imported):")
    for u in unused:
        # Ignore main entry points
        if u not in ['app', 'main', 'scheduler', 'trigger_server', 'generate_historical_backtests', 'generate_long_term_backtests', 'test_sse_client']:
            print(f"- {u}.py")
            
    print("\nEntry points or standalone scripts:")
    for u in unused:
        if u in ['app', 'main', 'scheduler', 'trigger_server', 'generate_historical_backtests', 'generate_long_term_backtests', 'test_sse_client']:
            print(f"- {u}.py")

if __name__ == '__main__':
    main()
