import sys
import os
from cx_Freeze import setup, Executable

# --- NOUVEAU : On aide cx_Freeze à trouver tes fichiers pendant la compilation ---
# Ainsi, il va les compiler et les cacher au lieu de demander à les copier en clair.
chemin_collab = os.path.join(os.path.abspath(os.path.dirname(__file__)), "collab")
sys.path.insert(0, chemin_collab)

# 1. Options de compilation
build_exe_options = {
    "packages": [
        "pygame",
        "tkinter",
        "docplex",
        "docplex.cp.solver.solver_local",
    ],
    
    # 2. Les fichiers et dossiers supplémentaires à copier
    "include_files": [
        ("data", "data"),
        ("assets", "assets"),
        (r"C:\Program Files\IBM\ILOG\CPLEX_Studio_Community2211\cpoptimizer\bin\x64_win64", "moteur_cplex"),
        ("collab", "collab")
    ],
    
    "excludes": [
        "pandas", 
        "numpy",
        "IPython", 
        "jupyter_client", 
        "jupyter_core", 
        "ipykernel", 
        "matplotlib_inline",
        "zmq", 
        "tornado",
        "prompt_toolkit",
        "traitlets",
        "PyInstaller",
        "debugpy",
        "jedi",
        "parso",
        "unittest", 
        "pydoc_data", 
        "lib2to3",
        "setuptools",
        "wheel",
        "sqlite3", 
        "curses", 
        "gevent",
        "greenlet",
        "xmlrpc",
        "zope"
    ]
}

# 3. Gestion de la console
# ASTUCE : Pour tes premiers tests, laisse "base = None" pour voir les erreurs dans la console noire.
# Quand tout marchera, remplace par "base = target_base" pour cacher la console.
target_base = None
if sys.platform == "win32":
    target_base = "Win32GUI" 

# Pour tester en voyant les erreurs, décommente la ligne ci-dessous :
base = None 
# Pour la version finale silencieuse, décommente la ligne ci-dessous :
#base = target_base 

# 4. Configuration finale
setup(
    name="OAD_Satellite",
    version="1.0",
    description="Expérience Interactive de Planification",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base=base, target_name="Experience_OAD.exe")]
)