from __future__ import annotations
import logging

from typing import Callable, Dict, List, Any, Tuple, TYPE_CHECKING

from src.fleetctrl.pooling.batch.InsertionHeuristic.BatchInsertionHeuristicAssignment import BatchInsertionHeuristicAssignment
from src.fleetctrl.pooling.immediate.insertion import immediate_insertion_with_heuristics, insert_prq_in_selected_veh_list
if TYPE_CHECKING:
    from src.simulation.Vehicles import SimulationVehicle
    from src.simulation.Legs import VehicleRouteLeg
    from src.fleetctrl.planning.PlanRequest import PlanRequest
    from src.fleetctrl.SemiOnDemandBatchAssignmentFleetcontrol import PtLine

LOG = logging.getLogger(__name__)

INPUT_PARAMETERS_BatchZonalInsertionHeuristicAssignment = {
    "doc" :  """this class uses a simple insertion heuristic to assign zonal requests in batch that havent been assigned before """,
    "inherit" : "BatchInsertionHeuristicAssignment",
    "input_parameters_mandatory": [],
    "input_parameters_optional": [
        ],
    "mandatory_modules": [],
    "optional_modules": []
}

class BatchZonalInsertionHeuristicAssignment(BatchInsertionHeuristicAssignment):
    def compute_new_vehicle_assignments(self, sim_time: int, vid_to_list_passed_VRLs: Dict[int, List[VehicleRouteLeg]],
                                        veh_objs_to_build: Dict[int, SimulationVehicle] = {},
                                        new_travel_times: bool = False, build_from_scratch: bool = False):
        """ this function computes new vehicle assignments based on current fleet information
        (adapted implementation for zonal constraints)
                param sim_time : current simulation time
                param vid_to_list_passed_VRLs : (dict) vid -> list_passed_VRLs; needed to update database and V2RBs
                :param veh_objs_to_build: only these vehicles will be optimized (all if empty) dict vid -> SimVehicle obj only for special cases needed in current alonso mora module
                :param new_travel_times : bool; if traveltimes changed in the routing engine
                :param build_from_scratch : only for special cases needed in current alonso mora module
                """


        self.sim_time = sim_time
        if len(veh_objs_to_build) != 0:
            raise NotImplementedError
        for rid in list(self.unassigned_requests.keys()):
            if self.rid_to_consider_for_global_optimisation.get(rid) is None:
                continue
            # if rid==10082:
            #     print("rid 10082")

            vid_to_exclude = {}
            # check flexible portion time to add vehicles to excluded_vid
            PT_line: PtLine = self.fleetcontrol.return_ptline()
            # rq_origin_fixed = not PT_line.check_request_flexible(self.fleetcontrol.rq_dict[rid], "origin")
            # rq_t_pu_earliest = self.fleetcontrol.rq_dict[rid].t_pu_earliest
            # assert rq_t_pu_earliest > 0
            # rq_t_pu_latest = self.fleetcontrol.rq_dict[rid].t_pu_latest
            # assert rq_t_pu_latest > 0
            if rid == 9992:
                print("rid 9344")
            #
            # for vid in self.fleetcontrol.veh_plans.keys():
            #     if rq_origin_fixed:
            #         if not (PT_line.is_time_fixed_portion(vid, rq_t_pu_earliest)
            #             and PT_line.is_time_fixed_portion(vid, rq_t_pu_latest)):
            #             vid_to_exclude[vid] = 1

            # add zonal constraints by adding veh not assigned to the same zone as the request in excluded_vid
            if self.fleetcontrol.n_zones > 1:
                pu_zone = PT_line.return_pos_zone(self.fleetcontrol.rq_dict[rid].o_pos)
                do_zone = PT_line.return_pos_zone(self.fleetcontrol.rq_dict[rid].d_pos)
                LOG.debug(f"rid {rid} pu_zone {pu_zone} do_zone {do_zone} pu_pos {self.fleetcontrol.rq_dict[rid].o_pos} do_pos {self.fleetcontrol.rq_dict[rid].d_pos}")
                # if request pick-up & drop-off in fixed route, then consider all vehicles
                if pu_zone == -1 and do_zone == -1:
                    pass
                # if pick-up & drop-off in different zones of flex routes, then ignore zonal vehicles
                elif pu_zone != do_zone and pu_zone != -1 and do_zone != -1:
                    for vid in self.fleetcontrol.veh_plans.keys():
                        veh_zone = PT_line.veh_zone_assignment[vid]
                        if veh_zone != -1:
                            vid_to_exclude[vid] = 1
                # otherwise, ignore all zonal vehicles but one zone
                else:
                    for vid in self.fleetcontrol.veh_plans.keys():
                        veh_zone = PT_line.veh_zone_assignment[vid]
                        if veh_zone != max(pu_zone, do_zone) and veh_zone != -1: # include specific zonal & regular vehicles
                        # if veh_zone != max(pu_zone, do_zone): # ignore regular vehicles too
                            vid_to_exclude[vid] = 1


            selected_veh_list = [veh for veh in self.fleetcontrol.sim_vehicles if veh.vid not in vid_to_exclude]
            LOG.debug(f"selected vehicles: {[veh.vid for veh in selected_veh_list]}")

            # TODO: use insert_prq_in_selected_veh_list(selected_veh_obj_list instead of post-exclusion of vid_to_exclude
            r_list = insert_prq_in_selected_veh_list(
                selected_veh_list, self.fleetcontrol.veh_plans, self.active_requests[rid], self.fleetcontrol.vr_ctrl_f,
                self.fleetcontrol.routing_engine, self.fleetcontrol.rq_dict, sim_time,
                self.fleetcontrol.const_bt, self.fleetcontrol.add_bt,
                True,  self.fleetcontrol.rv_heuristics
            )
            # r_list = immediate_insertion_with_heuristics(
            #     sim_time, self.active_requests[rid], self.fleetcontrol
            # )

            # adapt r_list to exclude vid in vid_to_exclude
            # r_list = [(vid, plan, obj) for vid, plan, obj in r_list if vid not in vid_to_exclude]

            LOG.debug(f"solution for rid {rid}:")
            # if rid==10082:
            #     print("rid 10082")
            for vid, plan, obj in r_list:
                LOG.debug(f"vid {vid} with obj {obj}:\n plan {plan}")
                # original plan
                LOG.debug(
                    f"original obj {self.fleetcontrol.veh_plans[vid].get_utility()} plan {self.fleetcontrol.veh_plans[vid]}")
            if len(r_list) != 0:
                best_vid, best_plan, _ = min(r_list, key=lambda x: x[2])
                self.fleetcontrol.assign_vehicle_plan(self.fleetcontrol.sim_vehicles[best_vid], best_plan, sim_time)
                # update utility
                veh_obj = self.fleetcontrol.sim_vehicles[best_vid]
                upd_utility_val = self.fleetcontrol.compute_VehiclePlan_utility(sim_time, veh_obj,
                                                                                self.fleetcontrol.veh_plans[best_vid])
                self.fleetcontrol.veh_plans[best_vid].set_utility(upd_utility_val)

                # del self.unassigned_requests[rid]

        self.unassigned_requests = {}  # only try once

    def register_change_in_time_constraints(self, rid: Any, prq: PlanRequest, assigned_vid: int = None,
                                            exceeds_former_time_windows: bool = True):
        # TODO: consider moving this to the base class (BatchAssignmentAlgorithmBase)
        pass
