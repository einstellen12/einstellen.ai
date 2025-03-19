import ast
import logging

logger = logging.getLogger('interview')

def evaluate_code(code):
    try:
        ast.parse(code)
        lines = code.split('\n')
        if len(lines) > 50:
            return 'Code is syntactically correct but overly complex.'
        return 'Code is syntactically correct and efficient.'
    except SyntaxError as e:
        logger.warning(f"Code evaluation failed: {e}")
        return f'Syntax error: {str(e)}'
    except Exception as e:
        logger.error(f"Unexpected error in code evaluation: {e}")
        return f'Code evaluation failed: {str(e)}'