from pwn import *
from tqdm import tqdm
import json

subprocess.check_call('yosys -p "read_verilog backdoor.v; flatten; synth -flatten -top backdoor; abc -g NAND; techmap -map not2nand.v; write_json backdoor.json"', shell=True)

design = json.load(open("backdoor.json", "r"))
decode = design["modules"]["backdoor"]
cells = decode["cells"]
ports = decode["ports"]

names = {}

for name, port in ports.items():
    if len(port["bits"]) == 1:
        names[port["bits"][0]] = name
    else:
        for i, bit in enumerate(port["bits"]):
            names[bit] = f"{name}_{i}"

for name, port in ports.items():
    if port["direction"] == "output": continue
    if len(port["bits"]) == 1:
        names[port["bits"][0]] = name
    else:
        for i, bit in enumerate(port["bits"]):
            names[bit] = f"{name}_{i}"

def get_wire_name(wire):
    return names.get(wire, f"{wire}")

gates = []

for cell in cells.values():
    a = cell["connections"]["A"][0]
    b = cell["connections"]["B"][0]
    y = cell["connections"]["Y"][0]
    gates += [(get_wire_name(y), get_wire_name(a), get_wire_name(b))]

for name, port in ports.items():
    if port["direction"] == "input": continue
    if any(name == y for (y, _, _) in gates): continue
    wire = get_wire_name(port["bits"][0])
    gates += [(f"{name}_n", wire, wire)]
    gates += [(f"{name}", f"{name}_n", f"{name}_n")]

gates += [
    ("pt_0_n", "pt_0", "pt_0"),
    ("one", "pt_0", "pt_0_n"),
    ("zero", "one", "one"),
]

print(len(gates))

#r = process("./challenge.py")
r = remote("localhost", 1337)

for gate in tqdm(gates):
    r.recvuntil(b"NAND> ")
    r.sendline(" ".join(gate).encode())

r.recvuntil(b"NAND> ")
r.sendline()

print(bytes.fromhex("".join(r.recvall().decode().split("\n"))).decode())