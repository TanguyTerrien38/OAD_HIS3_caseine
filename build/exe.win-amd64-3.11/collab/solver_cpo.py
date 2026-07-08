import time
import pygame 
import math
from docplex.cp.config import context
from docplex.cp.model import CpoModel

# Force la recherche locale
context.solver.agent = 'local'

class MockSolution:
    """Imposteur qui mime le comportement d'une solution CPLEX."""
    def __init__(self):
        self.var_states = {}

    def set_var(self, var, start, end, present):
        if var is not None:
            self.var_states[var.get_name()] = (start, end, present)

    def get_var_solution(self, var):
        state = self.var_states.get(var.get_name() if var else "", (0, 0, False))
        class VarSol:
            def get_start(self): return state[0]
            def get_end(self): return state[1]
            def is_present(self): return state[2]
        return VarSol()

class PlanningSolver:
    def __init__(self, tasks, operators):
        self.tasks = tasks
        self.operators = operators
        self.mdl = CpoModel()
        self.constraint_names = []
        
        self.op_name_to_id = {op.name: op.id for op in operators}
        self.op_id_to_name = {op.id: op.name for op in operators}
                
        self.pools = {}
        for op in operators:
            self.pools.setdefault(op.pool_name, []).append(op.id)
            
        self.jobs = {}
        for t in tasks:
            self.jobs.setdefault(t.activity_id, []).append(t)
            
        for act_id in self.jobs:
            self.jobs[act_id].sort(key=lambda x: (x.id, getattr(x, 'part_index', 0)))

        # Variables d'instance pour le modèle
        self.WS = {}
        self.opt_WS = {op.id: {} for op in self.operators}
        self.tasks_to_include = []
        self.target_keys = []
        self.min_start_day = 0
        self.overlap_penalties = []

    def tk(self, t): 
        return (t.id, t.activity_id, t.part_index)
    
    def tk2(self, t): 
        return (getattr(t, 'activity_id', 'global'), t.id, getattr(t, 'part_index', 0))

    def add_named_ctr(self, ctr, name):
        ctr.set_name(name)
        self.mdl.add(ctr)
        self.constraint_names.append(name)


    def _run_heuristic_tetris(self, fixed_tasks, movable_tasks, replan_ref, max_horizon=150):
        timeline = {op.id: [False] * max_horizon for op in self.operators}
        
        for op in self.operators:
            for start, end in getattr(op, 'absences', []):
                for d in range(int(start), int(end)):
                    if d < max_horizon: timeline[op.id][d] = True
                    
        job_ends = {}
        sol = MockSolution()
        
        # 1. On replace les tâches figées à leur VRAIE place historique
        for t in fixed_tasks:
            k = self.tk(t)
            
            # Lecture des vraies coordonnées avant la destruction UI
            if k in replan_ref:
                start = int(math.floor(replan_ref[k]["start"]))
                op_name = replan_ref[k]["op"]
                op_id = self.op_name_to_id.get(op_name)
            else:
                start = int(math.floor(getattr(t, 'week_start', 0)))
                op_id = self.op_name_to_id.get(t.assigned_to)
                
            num_shifts = int(t.duration // 8)
            for i in range(num_shifts):
                if start + i < max_horizon and op_id:
                    timeline[op_id][start + i] = True
            job_ends[t.activity_id] = max(job_ends.get(t.activity_id, 0), start + num_shifts)
            
            # Enregistrement dans la solution
            if k in self.WS:
                for i in range(len(self.WS[k])):
                    d = start + i
                    sol.set_var(self.WS[k][i], d, d+1, True)
                    for op in self.operators:
                        if op.id in self.opt_WS and k in self.opt_WS[op.id] and i < len(self.opt_WS[op.id][k]):
                            sol.set_var(self.opt_WS[op.id][k][i], d, d+1, (op.id == op_id))
                            
        # 2. On insère les tâches à placer
        movable_tasks_sorted = sorted(movable_tasks, key=lambda x: (x.activity_id, x.id))
        
        for t in movable_tasks_sorted:
            k = self.tk(t)
            num_shifts = int(t.duration // 8)
            valid_ops = [self.op_name_to_id[t.forced_op]] if getattr(t, 'forced_op', None) else self.pools.get(t.pool_name, [])
            
            min_d = max(self.min_start_day, job_ends.get(t.activity_id, 0))
            best_op = None
            best_days = []
            
            for op_id in valid_ops:
                days = []
                d = min_d
                while len(days) < num_shifts and d < max_horizon:
                    if not timeline[op_id][d]:
                        is_unavail = any(u_s <= d < u_e for u_s, u_e in getattr(t, 'unavailabilities', []))
                        if not is_unavail:
                            days.append(d)
                    d += 1
                
                if len(days) == num_shifts:
                    if not best_days or days[0] < best_days[0]:
                        best_days = days
                        best_op = op_id
                        
            if not best_days:
                return None # Impossible de placer, on abandonne ce scénario
                
            for i, d in enumerate(best_days):
                timeline[best_op][d] = True
                if k in self.WS and i < len(self.WS[k]):
                    sol.set_var(self.WS[k][i], d, d+1, True)
                    for op in self.operators:
                        if op.id in self.opt_WS and k in self.opt_WS[op.id] and i < len(self.opt_WS[op.id][k]):
                            sol.set_var(self.opt_WS[op.id][k][i], d, d+1, (op.id == best_op))
                            
            job_ends[t.activity_id] = max(job_ends.get(t.activity_id, 0), best_days[-1] + 1)
            
        return sol

    # =========================================================================
    # ORCHESTRATEUR PRINCIPAL
    # =========================================================================
    def solve(self, time_limit=3, target_tasks=None, mode="no_conflict", seed=3, current_day=0.0, lower_bound=0.0, exact_makespan=None, radar_targets=None, replan_ref=None, global_deadline=None, conflict_tasks=None, pre_solve_state=None):        
        self.min_start_day = int(math.ceil(current_day - 0.05))
        
        combined_targets = (target_tasks or []) + (conflict_tasks or [])
        self.target_keys = [self.tk(t) for t in combined_targets]
        
        if target_tasks:
            for t in target_tasks: 
                t.assigned_to = None
            self.tasks_to_include = [t for t in self.tasks if t.assigned_to is not None or self.tk(t) in self.target_keys]
        else:
            self.tasks_to_include = self.tasks

        max_horizon = global_deadline if global_deadline is not None else 60
        is_replanning = (replan_ref is not None)

        self._build_variables(max_horizon)
        self._build_base_constraints(min_start_day=self.min_start_day)
        
        # On signale si on est en replanification pour éviter le double figeage !
        self._build_conflict_constraints(target_tasks, mode, is_replanning)

        if is_replanning:
            sol = self._solve_replan(time_limit, seed, replan_ref, self.min_start_day, conflict_tasks, mode)
        elif radar_targets:
            self._apply_radar_objectives(radar_targets)
            sol = self._solve_radar(time_limit, seed)
        else:
            self._apply_default_objectives(lower_bound, exact_makespan, target_tasks, mode)
            sol = self._solve_default(time_limit, seed)

        if sol:
            self._process_radar_metrics(sol)
            # print(self.solution_metrics)
            if radar_targets and not target_tasks:
                self._process_radar_metrics(sol)
            
            unassigned_tasks = target_tasks if target_tasks else [t for t in self.tasks_to_include if t.assigned_to is None]

            # 1. ON APPLIQUE LA SOLUTION SUR LES TÂCHES D'ABORD
            self._apply_solution_to_tasks(sol, unassigned_tasks)

            changes = []
            # 2. ON GÉNÈRE LES MESSAGES EN LISANT LES TÂCHES MISES À JOUR
            if is_replanning and pre_solve_state is not None:
                changes = self._generate_replan_messages(pre_solve_state)

            if is_replanning:
                return True, changes

            return True, "OK"
        else:
            return False, "Contraintes incompatibles"

    # =========================================================================
    # CONSTRUCTION DU MODÈLE (Variables & Contraintes)
    # =========================================================================
    def _build_variables(self, max_horizon):
        for op in self.operators:
            for t in self.tasks_to_include:
                self.opt_WS[op.id][self.tk(t)] = []

        for t in self.tasks_to_include:
            k = self.tk(t)
            k_str = f"{k[0]}_{k[1]}_{k[2]}" # NOUVEAU : Sécurisation du nom complet
            if hasattr(t, 'task_delay') and t.task_delay > 0:
                t.duration += t.task_delay
                t.task_delay = 0

            num_shifts = int(t.duration // 8)
            self.WS[k] = []
            
            forced_op_name = getattr(t, 'forced_op', None)
            valid_ops = [self.op_name_to_id[forced_op_name]] if forced_op_name and forced_op_name in self.op_name_to_id else self.pools.get(t.pool_name, [])

            for i in range(num_shifts):
                shift_var = self.mdl.interval_var(size=1, end=(0, max_horizon), name=f"T_{k_str}_S{i}")
                self.WS[k].append(shift_var)

                alts = []
                for oid in valid_ops:
                    alt_var = self.mdl.interval_var(optional=True, size=1, end=(0, max_horizon), name=f"Opt_Ope{oid}_T_{k_str}_S{i}")
                    alts.append(alt_var)
                
                for oid, opt_var in zip(valid_ops, alts):
                    self.opt_WS[oid][k].append(opt_var)
                    
                self.mdl.add(self.mdl.alternative(shift_var, alts))

    def _build_base_constraints(self, min_start_day):
        for t in self.tasks_to_include:
            k = self.tk(t)
            k_str = f"{k[0]}_{k[1]}_{k[2]}" 
            num_shifts = len(self.WS[k])

            t_unavails = []
            if hasattr(t, 'unavailabilities'):
                for u_s, u_e in t.unavailabilities:
                    u_start, u_end = int(u_s), int(u_e)
                    if u_end > u_start:
                        t_unavails.append(self.mdl.interval_var(size=u_end-u_start, start=u_start, end=u_end, name=f"Unavail_{k_str}_{u_start}"))
            
            if t_unavails and t.assigned_to is None:
                self.add_named_ctr(self.mdl.no_overlap(self.WS[k] + t_unavails), f"Task_Unavail_{k_str}")

            if t.assigned_to is None:
                self.add_named_ctr(self.mdl.start_of(self.WS[k][0]) >= min_start_day, f"Temps_min_{k_str}")

            deadline = getattr(t, 'deadline', None)
            if deadline is not None:
                self.add_named_ctr(self.mdl.end_of(self.WS[k][-1]) <= int(deadline), f"Deadline_{k_str}")
            
            for i in range(num_shifts - 1):
                self.add_named_ctr(self.mdl.end_before_start(self.WS[k][i], self.WS[k][i+1]), f"Ordre_interne_{k_str}")

    def _build_conflict_constraints(self, target_tasks, mode, is_replanning=False):
        for op in self.operators:
            absence_vars = []
            if hasattr(op, 'absences'):
                for abs_start, abs_end in op.absences:
                    start_int, end_int = int(abs_start), int(abs_end)
                    if end_int > start_int:
                        absence_vars.append(self.mdl.interval_var(size=end_int-start_int, start=start_int, end=end_int, name=f"Absence_{op.name}_{start_int}"))

            target_shifts, frozen_shifts = [], []
            for t in self.tasks_to_include:
                k = self.tk(t)
                if k in self.opt_WS[op.id]:
                    shifts = self.opt_WS[op.id][k]
                    (target_shifts if t.assigned_to is None else frozen_shifts).extend(shifts)

            if target_tasks:
                if len(target_shifts) > 1:
                    self.add_named_ctr(self.mdl.no_overlap(target_shifts), f"Target_Self_No_Overlap_{op.name}")
                for t_shift in target_shifts:
                    if mode == "no_conflict":
                        for f_shift in frozen_shifts + absence_vars:
                            self.add_named_ctr(self.mdl.no_overlap([t_shift, f_shift]), f"Target_vs_Frozen_{op.name}")
                    elif mode == "early":
                        if absence_vars:
                            self.add_named_ctr(self.mdl.no_overlap([t_shift] + absence_vars), f"Target_vs_Abs_{op.name}")
                        for f_shift in frozen_shifts:
                            self.overlap_penalties.append(self.mdl.overlap_length(t_shift, f_shift))
                    elif absence_vars:
                        self.add_named_ctr(self.mdl.no_overlap([t_shift] + absence_vars), f"Target_vs_Abs_{op.name}")
            else:
                all_shifts = target_shifts + frozen_shifts + absence_vars
                if all_shifts:
                    self.add_named_ctr(self.mdl.no_overlap(all_shifts), f"Chevauchement_Global_{op.name}")

        for act_id, job_tasks in self.jobs.items():
            vt = [t for t in job_tasks if t in self.tasks_to_include]
            grouped_by_id = []
            for t in vt:
                if not grouped_by_id or grouped_by_id[-1][0].id != t.id:
                    grouped_by_id.append([t])
                else:
                    grouped_by_id[-1].append(t)
            
            for group in grouped_by_id:
                if len(group) > 1:
                    all_shifts_for_this_id = []
                    for t in group:
                        all_shifts_for_this_id.extend(self.WS[self.tk(t)])                    
                    self.add_named_ctr(self.mdl.no_overlap(all_shifts_for_this_id), f"No_Overlap_ID_{group[0].id}")

            for i in range(len(grouped_by_id) - 1):
                for t1 in grouped_by_id[i]:
                    for t2 in grouped_by_id[i+1]:
                        k1, k2 = self.tk(t1), self.tk(t2)
                        k1_str = f"{k1[0]}_{k1[1]}_{k1[2]}" 
                        k2_str = f"{k2[0]}_{k2[1]}_{k2[2]}" 
                        if (t1.assigned_to is not None and k1 not in self.target_keys) and (t2.assigned_to is not None and k2 not in self.target_keys):
                            continue     
                        self.add_named_ctr(self.mdl.end_before_start(self.WS[k1][-1], self.WS[k2][0]), f"Precedence_Externe_{k1_str}_to_{k2_str}")

        if not is_replanning:
            for t in self.tasks_to_include:
                k = self.tk(t)
                k_str = f"{k[0]}_{k[1]}_{k[2]}" 
                if t.assigned_to is not None and k not in self.target_keys:
                    assigned_op_id = self.op_name_to_id.get(t.assigned_to)
                    if assigned_op_id in self.opt_WS and k in self.opt_WS[assigned_op_id] and k in self.WS:
                        for i, interval_var in enumerate(self.opt_WS[assigned_op_id][k]):
                            self.add_named_ctr(self.mdl.presence_of(interval_var) == 1, f"Fige_op_{k_str}")
                            if i < len(self.WS[k]):
                                self.add_named_ctr(self.mdl.start_of(self.WS[k][i]) == int(t.week_start) + i, f"Fige_jour_{k_str}")

    # =========================================================================
    # OBJECTIFS SPÉCIFIQUES
    # =========================================================================
    def _apply_default_objectives(self, lower_bound, exact_makespan, target_tasks=None, mode="normal"):
        makespan = self.mdl.max([self.mdl.end_of(self.WS[self.tk(t)][-1]) for t in self.tasks_to_include]) if self.tasks_to_include else 0
        op_change_penalty = []
        
        for t in self.tasks_to_include:
            k = self.tk(t)
            num_shifts = len(self.WS[k]) if k in self.WS else 0
            if num_shifts > 1:
                for i in range(num_shifts - 1):
                    for op in self.operators:
                        if op.id in self.opt_WS and k in self.opt_WS[op.id] and len(self.opt_WS[op.id][k]) > i + 1:
                            presence_i = self.mdl.presence_of(self.opt_WS[op.id][k][i])
                            presence_next = self.mdl.presence_of(self.opt_WS[op.id][k][i+1])
                            op_change_penalty.append(self.mdl.abs(presence_i - presence_next) * 5)
                            
        # 1. Force d'attraction vers la gauche (x1000)
        early_pull = []
        if mode == "early" and target_tasks:
            for t in target_tasks:
                k = self.tk(t)
                if k in self.WS:
                    for shift in self.WS[k]:
                        early_pull.append(self.mdl.start_of(shift) * 1000)
        
        # 2. Consolidation des pénalités
        total_penalty = 0
        if early_pull: total_penalty += self.mdl.sum(early_pull)
        if op_change_penalty: total_penalty += self.mdl.sum(op_change_penalty)
        if hasattr(self, 'overlap_penalties') and self.overlap_penalties:
            total_penalty += self.mdl.sum(self.overlap_penalties) * 10 # Force de répulsion (x10)

        # 3. Application au modèle
        if exact_makespan is not None:
            self.mdl.add(makespan == int(math.floor(exact_makespan)))
            if not isinstance(total_penalty, int) or total_penalty > 0:
                self.mdl.add(self.mdl.minimize(total_penalty))
        elif lower_bound > 0:
            self.mdl.add(makespan >= int(math.floor(lower_bound)))
            self.mdl.add(self.mdl.minimize(makespan * 10000 + total_penalty))
        else:
            self.mdl.add(self.mdl.minimize(makespan * 10000 + total_penalty))

    def _apply_radar_objectives(self, radar_targets):
        # 1. MAKESPAN
        makespan = self.mdl.max([self.mdl.end_of(self.WS[self.tk(t)][-1]) for t in self.tasks_to_include]) if self.tasks_to_include else 0
        
        # 2. IDLE TIME
        op_idles = []
        for op in self.operators:
            op_ivs = [iv for t in self.tasks_to_include for iv in self.opt_WS.get(op.id, {}).get(self.tk(t), [])]
            if op_ivs:
                op_span = self.mdl.interval_var(optional=True)
                self.mdl.add(self.mdl.span(op_span, op_ivs))
                op_worked = self.mdl.sum([self.mdl.presence_of(iv) for iv in op_ivs])
                op_idles.append(self.mdl.max(0, self.mdl.length_of(op_span, 0) - op_worked))
        idle_time = self.mdl.sum(op_idles) * 8 if op_idles else 0

        # 3. BALANCE
        op_loads = {}
        for op in self.operators:
            op_ivs = [iv for t in self.tasks_to_include for iv in self.opt_WS.get(op.id, {}).get(self.tk(t), [])]
            op_loads[op.id] = self.mdl.sum([self.mdl.presence_of(iv) for iv in op_ivs]) * 8 if op_ivs else 0
            
        pool_devs = []
        for pool_name, pool_op_ids in self.pools.items():
            N_p = len(pool_op_ids)
            if N_p > 0:
                sum_p = sum(op_loads[oid] for oid in pool_op_ids)
                for oid in pool_op_ids:
                    pool_devs.append(self.mdl.abs(N_p * op_loads[oid] - sum_p) // N_p)
        
        N_total = len(self.operators)
        balance = (self.mdl.sum(pool_devs) // N_total) if N_total > 0 and pool_devs else 0

        # 4. WIP
        job_wips = []
        for act_id, job_tasks in self.jobs.items():
            vt = [t for t in job_tasks if t in self.tasks_to_include]
            if vt:
                span_expr = self.mdl.end_of(self.WS[self.tk(vt[-1])][-1]) - self.mdl.start_of(self.WS[self.tk(vt[0])][0])
                active_days = sum(len(self.WS[self.tk(t)]) for t in vt)
                job_wips.append(span_expr - active_days)
                
        wip = (self.mdl.sum(job_wips) // len(job_wips)) if job_wips else 0

        # --- ASSOCIATION AUX CIBLES DU RADAR ---
        metric_expressions = {
            "makespan": makespan, 
            "idle_time": idle_time,
            "balance": balance,
            "wip": wip
        } 
        
        for m_id, target in radar_targets.items():
            if m_id in metric_expressions:
                if target['type'] == 'exact':
                    self.add_named_ctr(metric_expressions[m_id] == target['val'], f"Radar_Exact_{m_id}")
                else:
                    self.add_named_ctr(metric_expressions[m_id] <= target['val'], f"Radar_Max_{m_id}")

        # =====================================================================
        # NOUVEL OBJECTIF : LISSAGE (Minimiser les pauses et changements)
        # =====================================================================
        penalties = []
        for t in self.tasks_to_include:
            k = self.tk(t)
            num_shifts = len(self.WS[k]) if k in self.WS else 0
            
            if num_shifts > 1:
                for i in range(num_shifts - 1):
                    # 1. Pénalité de Pause (Gap) : si le shift i+1 ne commence pas immédiatement après le i
                    gap = self.mdl.start_of(self.WS[k][i+1]) - self.mdl.end_of(self.WS[k][i])
                    penalties.append(gap * 10)  # Poids de 10 par jour de pause
                    
                    # 2. Pénalité de Changement d'Opérateur
                    for op in self.operators:
                        if op.id in self.opt_WS and k in self.opt_WS[op.id] and len(self.opt_WS[op.id][k]) > i + 1:
                            p_curr = self.mdl.presence_of(self.opt_WS[op.id][k][i])
                            p_next = self.mdl.presence_of(self.opt_WS[op.id][k][i+1])
                            # Si p_curr (présent sur le shift 1) est différent de p_next (présent sur shift 2), on pénalise !
                            penalties.append(self.mdl.abs(p_curr - p_next) * 50) 

        # On demande au solveur de minimiser l'ensemble de ces pénalités
        if penalties:
            self.mdl.add(self.mdl.minimize(self.mdl.sum(penalties)))

    # =========================================================================
    # RÉSOLUTION (Les 3 moteurs)
    # =========================================================================
    def _solve_default(self, time_limit, seed):
        return self.mdl.solve(TimeLimit=time_limit, trace_log=0, RandomSeed=seed, SearchType='Restart')

    def _solve_radar(self, time_limit, seed):
        search = self.mdl.start_search(TimeLimit=time_limit, trace_log=0, RandomSeed=seed, SearchType='Restart')
        first_sol_time = None
        last_sol = None
        
        for current_sol in search:
            last_sol = current_sol
            if first_sol_time is None: 
                first_sol_time = time.time()
            if time.time() - first_sol_time >= 1.0: 
                return last_sol
                
        return last_sol

    def _solve_replan(self, time_limit, seed, replan_ref, min_start_day, conflict_tasks=None, mode="normal", pre_solve_state=None):
        # print(f"Démarrage Replanification (Mode: {mode})...")
        
        conflict_keys = {self.tk(t) for t in (conflict_tasks or [])}
        
        tasks_to_move = []
        tasks_to_freeze = []
        new_tasks = []
        
        # 1. Tri chirurgical
        for t in self.tasks_to_include:
            k = self.tk(t)
            is_in_history = (k in replan_ref)
            is_conflict = (k in conflict_keys)
            is_released = (t.assigned_to is None)
            
            is_truly_new = (not is_in_history) and is_released
            
            if is_released or is_conflict or is_truly_new:
                tasks_to_move.append(t)
                if is_truly_new:
                    new_tasks.append(t)
            else:
                tasks_to_freeze.append(t)

        penalties = []

        # =====================================================================
        # 2. VRAI FIGEAGE (Hard Freeze)
        # =====================================================================
        for t in tasks_to_freeze:
            k = self.tk(t)
            if k in self.WS:
                old_start = int(math.floor(replan_ref.get(k, {}).get("start", getattr(t, 'week_start', 0))))
                old_op_name = replan_ref.get(k, {}).get("op", t.assigned_to)
                old_op_id = self.op_name_to_id.get(old_op_name)
                
                for i in range(len(self.WS[k])):
                    # Contrainte stricte de date
                    self.mdl.add(self.mdl.start_of(self.WS[k][i]) == old_start + i)
                    # Contrainte stricte d'opérateur
                    if old_op_id and old_op_id in self.opt_WS and k in self.opt_WS[old_op_id] and len(self.opt_WS[old_op_id][k]) > i:
                        self.mdl.add(self.mdl.presence_of(self.opt_WS[old_op_id][k][i]) == 1)

        # =====================================================================
        # 3. OBJECTIFS POUR LES TÂCHES À DÉPLACER
        # =====================================================================
        historical_moves = []
        new_moves = []
        
        # On sépare proprement les tâches avec un historique et les vraies nouvelles
        for t in tasks_to_move:
            k = self.tk(t)
            if k in replan_ref:
                historical_moves.append(t)
            else:
                new_moves.append(t)

        # --- A. TÂCHES HISTORIQUES (Chaque morceau vise sa place d'origine exacte) ---
        for t in historical_moves:
            k = self.tk(t)
            if k not in self.WS: continue
            
            old_start = int(math.floor(replan_ref[k]["start"]))
            old_op_id = self.op_name_to_id.get(replan_ref[k]["op"])
            num_shifts = len(self.WS[k])
            
            for i in range(num_shifts):
                expected_start = old_start + i
                penalties.append(self.mdl.abs(self.mdl.start_of(self.WS[k][i]) - expected_start) * 10)
                
                if old_op_id and old_op_id in self.opt_WS and k in self.opt_WS[old_op_id] and len(self.opt_WS[old_op_id][k]) > i:
                    changed = 1 - self.mdl.presence_of(self.opt_WS[old_op_id][k][i])
                    penalties.append(changed * 30)

        # --- B. NOUVELLES TÂCHES (On les fusionne par ID pour garantir la continuité) ---
        grouped_new = {}
        for t in new_moves:
            g_key = (getattr(t, 'activity_id', 'global'), t.id)
            grouped_new.setdefault(g_key, []).append(t)
            
        for g_key, group in grouped_new.items():
            group.sort(key=lambda x: getattr(x, 'part_index', 0))
            
            all_shifts = []
            all_opt_shifts = []
            for t in group:
                k = self.tk(t)
                if k in self.WS:
                    for i in range(len(self.WS[k])):
                        all_shifts.append(self.WS[k][i])
                        opt_dict = {}
                        for op in self.operators:
                            if op.id in self.opt_WS and k in self.opt_WS[op.id] and len(self.opt_WS[op.id][k]) > i:
                                opt_dict[op.id] = self.opt_WS[op.id][k][i]
                        all_opt_shifts.append(opt_dict)
                        
            num_shifts = len(all_shifts)
            if num_shifts == 0: continue
            
            # Poussée vers la gauche
            if mode == "early":
                for i in range(num_shifts):
                    penalties.append(self.mdl.start_of(all_shifts[i]) * 1000)
            else:
                for i in range(num_shifts):
                    penalties.append(self.mdl.start_of(all_shifts[i]) * 2)
                    
            if num_shifts > 1:
                for i in range(num_shifts - 1):
                    # On évite que la tâche soit fragmentée dans le temps
                    gap = self.mdl.start_of(all_shifts[i+1]) - self.mdl.end_of(all_shifts[i])
                    penalties.append(self.mdl.abs(gap) * 50)
                    
                    # On garde le même opérateur tout du long
                    for op in self.operators:
                        if op.id in all_opt_shifts[i] and op.id in all_opt_shifts[i+1]:
                            p_current = self.mdl.presence_of(all_opt_shifts[i][op.id])
                            p_next = self.mdl.presence_of(all_opt_shifts[i+1][op.id])
                            penalties.append(self.mdl.abs(p_current - p_next) * 50)

        # =====================================================================
        # 4. REGROUPEMENT PAR OPÉRATEUR (Pour les nouvelles tâches)
        # =====================================================================
        if new_moves:
            op_used_vars = []
            for op in self.operators:
                shifts_on_op = [v for t in new_moves for v in self.opt_WS.get(op.id, {}).get(self.tk(t), [])]
                if shifts_on_op:
                    op_used_vars.append(self.mdl.max([self.mdl.presence_of(v) for v in shifts_on_op]))
            if op_used_vars:
                penalties.append(self.mdl.sum(op_used_vars) * 5000)

        # =====================================================================
        # 5. RÉSOLUTION
        # =====================================================================
        if penalties or (hasattr(self, 'overlap_penalties') and self.overlap_penalties):
            obj_expr = 0
            if penalties:
                obj_expr += self.mdl.sum(penalties)
            if hasattr(self, 'overlap_penalties') and self.overlap_penalties:
                obj_expr += self.mdl.sum(self.overlap_penalties) * 10
            self.mdl.add(self.mdl.minimize(obj_expr))

        # print(f"CPLEX : {len(tasks_to_freeze)} figées DUREMENT, {len(tasks_to_move)} à replacer (dont {len(new_tasks)} nouvelles).")        
        sol = self.mdl.solve(TimeLimit=time_limit, trace_log=0, RandomSeed=seed, SearchType='Auto')
        # print(sol.get_objective_value())
        return sol

    # =========================================================================
    # POST-TRAITEMENT ET MÉTRIQUES
    # =========================================================================
    def _evaluate_solution(self, sol, eval_data, current_best_score):
        score = 0
        get_var = sol.get_var_solution 
        
        for data in eval_data:
            num_shifts = data['num_shifts']
            
            for i in range(num_shifts):
                main_var_sol = get_var(data['main_vars'][i])
                diff_date = abs(main_var_sol.get_start() - (data['old_start'] + i))
                
                if diff_date > 0:
                    score += diff_date * 10
                    if score >= current_best_score: return float('inf')
                
                if i < num_shifts - 1:
                    gap = get_var(data['main_vars'][i+1]).get_start() - main_var_sol.get_end()
                    if gap > 0:
                        score += gap * 20
                        if score >= current_best_score: return float('inf')
                
                assigned_op = next((name for name, var in data['op_vars'][i] if get_var(var).is_present()), None)
                if assigned_op != data['old_op']:
                    score += 30
                    if score >= current_best_score: return float('inf')
        return score

    def _apply_solution_to_tasks(self, sol, unassigned_tasks):
        current_time_ms = pygame.time.get_ticks()
        
        for t in unassigned_tasks:
            k = self.tk(t)
            t.solved_time = current_time_ms
            num_shifts = int(t.duration // 8)

            shifts_info = []
            for i in range(num_shifts):
                start = sol.get_var_solution(self.WS[k][i]).get_start()
                
                # Remplacement du générateur par une boucle claire pour extraire l'opérateur
                op_chosen = None
                for oid in self.pools.get(t.pool_name, []):
                    if k in self.opt_WS[oid] and i < len(self.opt_WS[oid][k]):
                        if sol.get_var_solution(self.opt_WS[oid][k][i]).is_present():
                            op_chosen = oid
                            break
                            
                shifts_info.append((start, op_chosen))
                
            shifts_info.sort(key=lambda x: x[0])

            blocks, curr_block = [], [shifts_info[0]]
            for i in range(1, num_shifts):
                if shifts_info[i][0] == curr_block[-1][0] + 1 and shifts_info[i][1] == curr_block[-1][1]:
                    curr_block.append(shifts_info[i])
                else:
                    blocks.append(curr_block)
                    curr_block = [shifts_info[i]]
            blocks.append(curr_block)

            t.week_start, t.duration = blocks[0][0][0], len(blocks[0]) * 8
            
            # Sécurité au cas où aucun opérateur n'a été assigné
            t.assigned_to = self.op_id_to_name.get(blocks[0][0][1])

            for op in self.operators:
                if op.name == t.assigned_to and t not in op.tasks: op.tasks.append(t)
            
            TaskClass, current_idx = type(t), self.tasks.index(t)
                            
            for i, block in enumerate(blocks[1:], 1):
                new_task = TaskClass(
                    id=t.id, name=t.name, activity_name=t.activity_name, duration=len(block)*8,
                    activity_id=t.activity_id, pool_name=t.pool_name, 
                    assigned_to=self.op_id_to_name.get(block[0][1]),
                    part_index=0, week_start=block[0][0], start_half=t.start_half, description=t.description, 
                    solved_time=current_time_ms, is_pinned=getattr(t, 'is_pinned', False)
                )
                self.tasks.insert(current_idx + i, new_task)
                for op in self.operators:
                    if op.name == new_task.assigned_to: op.tasks.append(new_task)

        # Mise à jour des index
        id_groups = {}
        for t in self.tasks: 
            group_key = (t.activity_id, t.id)
            id_groups.setdefault(group_key, []).append(t)
        for group in id_groups.values():
            if len(group) > 1:
                for i, t in enumerate(sorted(group, key=lambda x: x.week_start if x.assigned_to else 9999)): 
                    t.part_index = i + 1
            elif group: 
                group[0].part_index = 0

    def _generate_replan_messages(self, pre_solve_state):
        changes = []
        for t in self.tasks_to_include:
            k = self.tk2(t)
            
            old_data = pre_solve_state.get(k)
            if not old_data:
                # Fallback pour les tâches ayant été coupées
                fallback_k = (k[0], k[1], 0)
                old_data = pre_solve_state.get(fallback_k)
                if not old_data:
                    continue 
                
            old_op, old_start_float, _ = old_data
            was_unassigned = (old_op is None or str(old_op).strip() in ["", "None"])
            
            old_start = int(math.floor(old_start_float)) if old_start_float is not None else 0
            old_op_str = str(old_op).strip() if not was_unassigned else None

            # ---> LECTURE DIRECTE SUR L'OBJET MIS À JOUR <---
            s_start = int(math.floor(t.week_start))
            s_op = str(t.assigned_to).strip() if t.assigned_to else None

            nom_base = f"{t.name} (P{t.part_index})" if getattr(t, 'part_index', 0) > 0 else t.name
            
            if was_unassigned:
                if s_op: # Sécurité : Vérifie que la tâche a bien été placée
                    changes.append(f"• {nom_base} : placé à J{s_start+1} avec {s_op}")
            else:
                if s_start != old_start or s_op != old_op_str:
                    msg_parts = []
                    if s_start != old_start: msg_parts.append(f"décalé à J{s_start+1}")
                    if s_op != old_op_str: msg_parts.append(f"réassigné à {s_op}")
                    changes.append(f"• {nom_base} : {' et '.join(msg_parts)}")
                        
        if not changes:
            changes.append("Aucune modification par rapport au plan initial.")
        return changes

    def _process_radar_metrics(self, sol):
        ms_val = max([sol.get_var_solution(self.WS[self.tk(t)][-1]).get_end() for t in self.tasks_to_include]) if self.tasks_to_include else 0
        
        real_idle_time_hours = 0
        for op in self.operators:
            op_starts, op_ends = [], []
            op_worked = 0
            for t in self.tasks_to_include:
                k = self.tk(t)
                if op.id in self.opt_WS and k in self.opt_WS[op.id]:
                    for i in range(len(self.opt_WS[op.id][k])):
                        sol_iv = sol.get_var_solution(self.opt_WS[op.id][k][i])
                        if sol_iv.is_present():
                            op_starts.append(sol_iv.get_start())
                            op_ends.append(sol_iv.get_end())
                            op_worked += 1
            if op_worked > 0:
                real_idle_time_hours += (max(op_ends) - min(op_starts) - op_worked) * 8

        real_loads = {}
        for op in self.operators:
            h = 0
            for t in self.tasks_to_include:
                k = self.tk(t)
                if op.id in self.opt_WS and k in self.opt_WS[op.id]:
                    for i in range(len(self.opt_WS[op.id][k])):
                        if sol.get_var_solution(self.opt_WS[op.id][k][i]).is_present():
                            h += 8
            real_loads[op.id] = h
            
        total_dev = 0
        for pool_name, pool_op_ids in self.pools.items():
            N_p = len(pool_op_ids)
            if N_p > 0:
                sum_p = sum(real_loads[oid] for oid in pool_op_ids)
                for oid in pool_op_ids:
                    total_dev += abs(N_p * real_loads[oid] - sum_p) // N_p
        
        N_total = len(self.operators)
        real_balance = total_dev // N_total if N_total > 0 else 0

        real_idles = []
        for act_id, job_tasks in self.jobs.items():
            vt = [t for t in job_tasks if t in self.tasks_to_include]
            if vt:
                span = sol.get_var_solution(self.WS[self.tk(vt[-1])][-1]).get_end() - sol.get_var_solution(self.WS[self.tk(vt[0])][0]).get_start()
                active_days = sum(len(self.WS[self.tk(t)]) for t in vt)
                real_idles.append(span - active_days)

        real_wip = sum(real_idles) // len(real_idles) if real_idles else 0

        self.solution_metrics = {
            "makespan": ms_val, 
            "balance": real_balance, 
            "wip": real_wip, 
            "idle_time": real_idle_time_hours
        }