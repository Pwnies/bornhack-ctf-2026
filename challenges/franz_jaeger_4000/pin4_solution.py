#!/usr/bin/env python3
"""
Z3 solver for Pin 4 arithmetic challenge
Solves the system of linear equations to find the 4-character solution
"""

from z3 import *


def solve_pin4():
    print("=== Pin 4 Z3 Solver ===")
    print("Solving the arithmetic constraints to find the 4-character pin...\n")
    
    # Create integer variables for the 4 characters
    x0, x1, x2, x3 = Ints('x0 x1 x2 x3')
    
    # Create Z3 solver
    solver = Solver()
    
    # Add the arithmetic constraints from the C code
    solver.add((x0 * 7) + (x1 * 3) + (x2 * 2) + (x3 * 1) == 1182)
    solver.add((x0 * 2) + (x1 * 5) + (x2 * 4) + (x3 * 3) == 1227)
    solver.add((x0 * 11) + (x1 * 13) + (x2 * 17) + (x3 * 19) == 5265)
    solver.add((x0 * 23) - (x1 * 29) + (x2 * 31) - (x3 * 37) == -3143)
    
    # Add ASCII constraints (printable characters)
    solver.add(x0 >= 32, x0 <= 126)
    solver.add(x1 >= 32, x1 <= 126)
    solver.add(x2 >= 32, x2 <= 126)
    solver.add(x3 >= 32, x3 <= 126)
    
    # Solve the system
    result = solver.check()
    
    if result == sat:
        model = solver.model()
        
        # Extract the solution
        char0 = model[x0].as_long()
        char1 = model[x1].as_long()
        char2 = model[x2].as_long()
        char3 = model[x3].as_long()
        
        print("Solution found")
        print(f"\nASCII values: {char0}, {char1}, {char2}, {char3}")
        print(f"Characters: '{chr(char0)}', '{chr(char1)}', '{chr(char2)}', '{chr(char3)}'")
        print(f"Pin 4 solution: {chr(char0)}{chr(char1)}{chr(char2)}{chr(char3)}")
        
        # Verify the solution
        print("\n=== Verification ===")
        check1 = (char0 * 7) + (char1 * 3) + (char2 * 2) + (char3 * 1)
        check2 = (char0 * 2) + (char1 * 5) + (char2 * 4) + (char3 * 3)
        check3 = (char0 * 11) + (char1 * 13) + (char2 * 17) + (char3 * 19)
        check4 = (char0 * 23) - (char1 * 29) + (char2 * 31) - (char3 * 37)
        
        return chr(char0) + chr(char1) + chr(char2) + chr(char3)
        
    elif result == unsat:
        print("✗ No solution exists for the given constraints!")
        return None
    else:
        print("✗ Solver timeout or unknown result!")
        return None

def numpy_solution():
    print("\n=== Alternative NumPy Solution ===")
    import numpy as np
    
    # Coefficient matrix: A
    A = np.array([
        [7, 3, 2, 1],
        [2, 5, 4, 3],
        [11, 13, 17, 19],
        [23, -29, 31, -37]
    ])
    
    # Constants vector: b
    b = np.array([1182, 1227, 5265, -3143])
    
    # Solve the system
    solution = np.linalg.solve(A, b)
    
    print("NumPy solution (should be integers):")
    print(f"x = {solution}")
    print(f"Rounded: {np.round(solution).astype(int)}")
    
    # Convert to characters
    chars = [chr(int(round(x))) for x in solution]
    print(f"Characters: {chars}")
    print(f"Pin: {''.join(chars)}")
        
if __name__ == "__main__":
    solution = solve_pin4()
    
    # Show alternative approach
    numpy_solution()
    
    print(f"\n=== Final Answer ===")
    if solution:
        print(f"Pin 4: {solution}")
    else:
        print("No solution found!")