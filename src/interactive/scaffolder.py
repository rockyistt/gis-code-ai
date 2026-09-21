#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scaffolder.py - Topology-driven multi-step interactive GIS script generator.

Built on physical-nesting and voltage-level topology patterns mined from 4,000+ real
workflows. After the user supplies a single step, the engine recommends the most
likely follow-up operations and automatically propagates primary/foreign-key IDs
and contextual attributes, producing a complete, runnable multi-step GIS script.
"""

import json
import re
import uuid
import random
from typing import Any, Dict, List, Optional, Tuple


class TopologyEngine:
    """Encodes GIS grid/spatial topology and produces follow-up recommendations."""
    
    # 1. MV substation equipment nesting (Installation -> Busbar -> Bay -> Conductor -> Termination)
    SUBSTATION_INTERNAL_CHAIN = [
        "E MS Installatie FP",
        "E MS Rail FP",
        "E MS Veld FP",
        "E MS Veld FP Geleider",
        "E MS Eindsluiting FP"
    ]
    
    # 2. Spatial station hierarchy (Complex -> Building -> Terrain)
    SUBSTATION_SPATIAL_CHAIN = [
        "E Stationcomplex",
        "E Station Gebouw",
        "E Station Terrein"
    ]
    
    # 3. Cable-and-splice physical pairings (Cable -> Joint)
    CABLE_AND_SPLICE_CHAINS = {
        "E MS Kabel": "E MS Mof",
        "E HS Kabel": "E HS Mof",
        "E LS Kabel": "E LS Mof",
        "E MS Verbinding": "E MS Kabel"
    }

    @classmethod
    def get_downstream_recommendations(cls, current_object: str, current_method: str) -> List[Dict[str, Any]]:
        """Return physically-plausible next-step recommendations for the given (object, method)."""
        recommendations = []
        obj_clean = current_object.strip()
        
        # 1. Equipment / spatial / cable cascade options (only after Create or Open)
        if "Create" in current_method or "Open" in current_method:
            # Substation physical asset nesting
            if obj_clean in cls.SUBSTATION_INTERNAL_CHAIN:
                idx = cls.SUBSTATION_INTERNAL_CHAIN.index(obj_clean)
                if idx < len(cls.SUBSTATION_INTERNAL_CHAIN) - 1:
                    next_obj = cls.SUBSTATION_INTERNAL_CHAIN[idx + 1]
                    recommendations.append({
                        "type": "physical_cascade",
                        "object": next_obj,
                        "method": "Create",
                        "description": f"Create downstream child asset [{next_obj}] (physical nesting: {obj_clean} -> {next_obj})"
                    })
            
            # Spatial hierarchy nesting
            elif obj_clean in cls.SUBSTATION_SPATIAL_CHAIN:
                idx = cls.SUBSTATION_SPATIAL_CHAIN.index(obj_clean)
                if idx < len(cls.SUBSTATION_SPATIAL_CHAIN) - 1:
                    next_obj = cls.SUBSTATION_SPATIAL_CHAIN[idx + 1]
                    recommendations.append({
                        "type": "spatial_cascade",
                        "object": next_obj,
                        "method": "Create",
                        "description": f"Create next-level spatial entity [{next_obj}] (spatial tree: {obj_clean} -> {next_obj})"
                    })
            
            # Cable-to-splice paired creation
            elif obj_clean in cls.CABLE_AND_SPLICE_CHAINS:
                next_obj = cls.CABLE_AND_SPLICE_CHAINS[obj_clean]
                recommendations.append({
                    "type": "cable_splice_association",
                    "object": next_obj,
                    "method": "Create",
                    "description": f"Create the physically-paired companion entity [{next_obj}]"
                })

        # 2. Lifecycle completion: after a Create we usually pair an Update and a Delete for a clean test case
        if "Create" in current_method:
            recommendations.append({
                "type": "lifecycle_update",
                "object": obj_clean,
                "method": "Update",
                "description": f"Update attributes of the just-created [{obj_clean}] (Update phase)"
            })
            recommendations.append({
                "type": "lifecycle_delete",
                "object": obj_clean,
                "method": "Delete",
                "description": f"Delete the just-created [{obj_clean}] to clean up the test-case lifecycle"
            })

        # 3. Always-available consistency check / view switch options (3103 Switch, 1661 Run in source data)
        recommendations.append({
            "type": "datamodel_check",
            "object": "datamodel_check",
            "method": "Run",
            "description": "Run datamodel consistency check"
        })
        recommendations.append({
            "type": "switch_view",
            "object": "Stationsschema",
            "method": "Switch",
            "description": "Switch view to the default Stationsschema (station network overview)"
        })

        return recommendations


class InteractiveScaffolder:
    """Core class for the interactive multi-step generator."""
    
    def __init__(self):
        # Track generated steps and a name->last_id pool used for FK predicate references
        self.steps = []
        self.last_created_ids = {}  # object_name -> last_id, used for FK lookups
        self.current_station = "6 002 005"   # default station number
        self.database = ":elektra"
        self.rag = None
        self.llm_predictor = None  # Lazy-loaded step-level LLM predictor
        
    def load_rag_engine(self, rag_index_dir: str = "data/processed/rag_index") -> bool:
        """
        Load the precomputed RAG semantic index so the scaffolder can map free-form
        natural-language input to real JSON step templates. Returns True on success.
        """
        # Disable TF/JAX backends in transformers to avoid heavy/incompatible imports
        import os as _os
        _os.environ.setdefault("USE_TF", "0")
        _os.environ.setdefault("USE_JAX", "0")
        _os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
        try:
            # Load rag_utils.py directly via spec, completely bypassing src.inference.__init__
            # (which eagerly imports HybridInferencer -> peft -> transformers -> tensorflow).
            import importlib.util as _ilu
            from pathlib import Path as _P
            rag_path = _P(__file__).resolve().parent.parent / "inference" / "rag_utils.py"
            spec = _ilu.spec_from_file_location("_rag_utils_standalone", str(rag_path))
            rag_utils = _ilu.module_from_spec(spec)
            spec.loader.exec_module(rag_utils)
            self.rag = rag_utils.StepRAG()
            self.rag.load(rag_index_dir)
            return True
        except Exception:
            self.rag = None
            return False
        
    def load_llm_predictor(self, model_dir: str = "models/step-level-model-865") -> bool:
        """
        Lazy-load the step-level LLM predictor (CodeLlama-7B + LoRA).
        Used as fallback when RAG doesn't find a high-confidence match.
        Returns True on success, False if model not available.
        """
        try:
            from src.inference.step_llm_predictor import StepLevelPredictor
            self.llm_predictor = StepLevelPredictor(
                model_dir=model_dir,
                verbose=False
            )
            return True
        except Exception as e:
            print(f"[WARN] LLM predictor not available: {e}")
            self.llm_predictor = None
            return False
        
    def parse_and_create_step_one(self, raw_prompt: str, use_rag: bool = False) -> Dict[str, Any]:
        """
        Parse the user's natural-language instruction and build the first GIS step JSON
        (with a fresh ID and context). When use_rag=True and the RAG index is loaded, the
        nearest real-world template is retrieved; otherwise a lightweight regex fallback is used.
        """
        expected_method, expected_obj = self._parse_method_and_object(raw_prompt)

        if use_rag and self.rag:
            try:
                results = self.rag.retrieve(raw_prompt, top_k=1)
                if results:
                    match = results[0]
                    method = match.get("method", "Create")
                    obj = match.get("object", "E MS Installatie FP")
                    if not self._is_rag_match_compatible(
                        expected_method,
                        expected_obj,
                        method,
                        obj,
                        match.get("score", 0.0),
                    ):
                        raise ValueError("RAG top hit is not compatible with requested method/object")
                    db = match.get("database", "elektra")
                    module = match.get("module", "Datamodel CRUD")
                    command = match.get("command", "")
                    test_data = match.get("test_data", {})
                    
                    # Generate a fresh ID and rewrite the template's primary key to avoid collisions
                    generated_id = str(random.randint(86393281400000, 86393281499999))
                    self.last_created_ids[obj] = generated_id
                    
                    if "create" in test_data and isinstance(test_data["create"], dict):
                        for cstm_key in ["FLD_CSTM", "FLD_CSTM0_0", "FLD_CSTM0_2"]:
                            if cstm_key in test_data["create"]:
                                test_data["create"][cstm_key]["ID"] = generated_id
                    
                    step_data = {
                        "step_index": 0,
                        "database": f":{db}" if not db.startswith(":") else db,
                        "object": obj,
                        "object_id": generated_id if method == "Create" else "Passed",
                        "module": module,
                        "method": "Open Object" if method == "Open" else method,
                        "command": command,
                        "test_data": test_data,
                        "_is_ai_predicted": True,
                        "_matched_instruction": match.get("instruction", "")
                    }
                    self.steps.append(step_data)
                    return step_data
            except Exception:
                pass  # Fall back to the regex parser below
                
        # Lightweight regex fallback (no RAG hit)
        method = expected_method
        obj = expected_obj

        # Generate the primary ID
        generated_id = str(random.randint(86393281400000, 86393281499999))
        self.last_created_ids[obj] = generated_id
        
        # Assemble the runnable step record (matches file_level_data format)
        step_data = {
            "step_index": 0,
            "database": self.database,
            "object": obj,
            "object_id": generated_id if method == "Create" else "Passed",
            "module": "Datamodel CRUD" if method in ["Create", "Update", "Delete"] else "Editor(s)",
            "method": "Open Object" if method == "Open" else method,
            "command": "Execute Datamodel CRUD Testcommand" if method in ["Create", "Update", "Delete"] else "Execute Object Control Testcommand",
            "test_data": self._generate_test_data_body(obj, method, generated_id),
            "_is_ai_predicted": False
        }
        
        self.steps.append(step_data)
        return step_data

    @staticmethod
    def _parse_method_and_object(raw_prompt: str) -> Tuple[str, str]:
        """Best-effort method/object parser used to guard RAG matches."""
        prompt_lower = raw_prompt.lower()
        method = "Create"
        if any(v in prompt_lower for v in ["open", "read", "view"]):
            method = "Open"
        elif any(v in prompt_lower for v in ["update", "modify", "edit", "change", "revise", "adjust"]):
            method = "Update"
        elif any(v in prompt_lower for v in ["delete", "remove", "destroy", "drop", "clean up", "cleanup"]):
            method = "Delete"
        elif any(v in prompt_lower for v in ["switch", "change schema"]):
            method = "Switch"
        elif any(v in prompt_lower for v in ["verify", "check"]):
            method = "Verify"

        obj = "E MS Installatie FP"
        known_objects = [
            "E MS Installatie FP",
            "E MS Rail FP",
            "E MS Veld FP Geleider",
            "E MS Veld FP",
            "E MS Eindsluiting FP",
            "E Stationcomplex",
            "E Station Gebouw",
            "E Station Terrein",
            "E MS Kabel",
            "E HS Kabel",
            "E LS Kabel",
            "E MS Mof",
            "E HS Mof",
            "E LS Mof",
        ]
        for candidate in known_objects:
            if candidate.lower() in prompt_lower:
                return method, candidate

        matched = re.search(
            r'(E\s+(?:HS|MS|LS)\s+.+?)(?:\s+where|\s+in\s+|$)',
            raw_prompt,
            re.IGNORECASE,
        )
        if matched:
            obj = matched.group(1).strip()
        elif "stationcomplex" in prompt_lower:
            obj = "E Stationcomplex"
        elif "gebouw" in prompt_lower or "building" in prompt_lower:
            obj = "E Station Gebouw"
        elif "terrein" in prompt_lower or "terrain" in prompt_lower:
            obj = "E Station Terrein"
        elif any(v in prompt_lower for v in ["ms cable", "mv cable", "medium voltage cable", "kabel"]):
            obj = "E MS Kabel"
        elif any(v in prompt_lower for v in ["hs cable", "hv cable", "high voltage cable"]):
            obj = "E HS Kabel"
        elif any(v in prompt_lower for v in ["ls cable", "lv cable", "low voltage cable"]):
            obj = "E LS Kabel"
        elif any(v in prompt_lower for v in ["ms joint", "mv joint", "medium voltage joint", "mof"]):
            obj = "E MS Mof"
        elif any(v in prompt_lower for v in ["hs joint", "hv joint", "high voltage joint"]):
            obj = "E HS Mof"
        elif any(v in prompt_lower for v in ["ls joint", "lv joint", "low voltage joint"]):
            obj = "E LS Mof"

        return method, obj

    @staticmethod
    def _normalize_method(method: str) -> str:
        method = (method or "").strip().lower()
        return "open" if method == "open object" else method

    @classmethod
    def _is_rag_match_compatible(
        cls,
        requested_method: str,
        requested_object: str,
        matched_method: str,
        matched_object: str,
        score: float,
    ) -> bool:
        if score < 0.55:
            return False
        method_ok = cls._normalize_method(requested_method) == cls._normalize_method(matched_method)
        object_ok = requested_object.strip().lower() == matched_object.strip().lower()
        return method_ok and object_ok

    def _retrieve_template_from_rag(self, method: str, obj: str) -> Optional[Dict[str, Any]]:
        """
        Query the RAG index for the closest real-world JSON template matching a
        given (method, object) pair. Returns the matched step_data dict if a
        high-confidence (score >= 0.55) hit is found, otherwise None.
        
        If RAG fails or score is low, attempts to use the step-level LLM predictor
        to generate the step from first principles.
        """
        if self.rag:
            try:
                query = f"{method} {obj}"
                results = self.rag.retrieve(query, top_k=3)
                for r in results:
                    if (r.get("method", "").lower() == method.lower() and
                            r.get("object", "").strip().lower() == obj.strip().lower()):
                        return r
            except Exception:
                pass
        
        # If RAG is unavailable or did not find anything, try the LLM predictor.
        return self._predict_with_llm(method, obj)
    
    def _predict_with_llm(self, method: str, obj: str) -> Optional[Dict[str, Any]]:
        """
        Use the step-level LLM predictor to generate a step template
        when RAG doesn't find a good match.
        """
        if self.llm_predictor is None:
            return None
        
        try:
            instruction = f"{method} {obj}"
            predicted = self.llm_predictor.predict_step(instruction)
            
            if predicted and isinstance(predicted, dict):
                # Add metadata to indicate this came from LLM prediction
                predicted["_llm_generated"] = True
                predicted["_llm_instruction"] = instruction
                return predicted
        except Exception:
            pass
        
        return None

    def build_cascade_step(
        self,
        recommendation: Dict[str, Any],
        prev_step: Dict[str, Any],
        template_match: Optional[Dict[str, Any]] = None,
        allow_template_lookup: bool = True,
    ) -> Dict[str, Any]:
        """
        Compose the next workflow step by combining the chosen recommendation with the
        previous step. Foreign-key references and IDs are propagated automatically. If a
        RAG index is loaded, the JSON template is sourced from real workflow data; otherwise
        a heuristic fallback template is used.
        """
        next_obj = recommendation["object"]
        next_method = recommendation["method"]
        prev_obj = prev_step["object"]
        prev_id = self.last_created_ids.get(prev_obj, "Passed")
        
        # Generate or reuse the target object ID
        next_id = "Passed"
        if next_method == "Create":
            next_id = str(random.randint(86393281400000, 86393281499999))
            self.last_created_ids[next_obj] = next_id
            
        step_index = len(self.steps)
        rag_match = template_match
        if rag_match is None and allow_template_lookup:
            rag_match = self._retrieve_template_from_rag(next_method, next_obj)
        
        # Build the test data body, inserting the foreign-key predicate referencing the parent ID
        test_data = {}
        if next_method == "Create":
            foreign_key_field = f"{prev_obj}"
            query_expr = f"gis_program_manager.cached_dataset(:elektra).collection(:{prev_obj.lower().replace(' ', '_')}).select(predicate.eq(:id,{prev_id})).an_element()"
            
            if rag_match and isinstance(rag_match.get("test_data"), dict):
                # Use the real-world source-data template, then patch ID + parent FK
                import copy
                td_clone = copy.deepcopy(rag_match["test_data"])
                create_block = td_clone.get("create", {})
                for cstm_key in list(create_block.keys()):
                    if cstm_key.startswith("FLD_CSTM") and isinstance(create_block[cstm_key], dict):
                        create_block[cstm_key]["ID"] = next_id
                        create_block[cstm_key][foreign_key_field] = query_expr
                        break
                test_data = td_clone
            else:
                test_data = {
                    "create": {
                        "Object": next_obj,
                        "Type": "Create",
                        "Dataset": self.database,
                        "Custom": "Yes",
                        f"FLD_CSTM0_{step_index}": {
                            foreign_key_field: query_expr,
                            "ID": next_id,
                        }
                    },
                    "update": {},
                    "editor": {},
                }
        
        elif next_method == "Update":
            target_id = self.last_created_ids.get(next_obj, next_id)
            if rag_match and isinstance(rag_match.get("test_data"), dict):
                import copy
                td_clone = copy.deepcopy(rag_match["test_data"])
                update_block = td_clone.get("update", {})
                for cstm_key in list(update_block.keys()):
                    if cstm_key.startswith("FLD_CSTM") and isinstance(update_block[cstm_key], dict):
                        update_block[cstm_key]["ID"] = target_id
                        break
                test_data = td_clone
            else:
                test_data = {
                    "create": {},
                    "update": {
                        "Object": next_obj,
                        "Type": "Update",
                        "Dataset": self.database,
                        "Custom": "Yes",
                        f"FLD_CSTM0_{step_index}": {
                            "ID": target_id,
                        }
                    },
                    "editor": {},
                }
            
        elif next_method == "Delete":
            test_data = {
                "create": {},
                "update": {},
                "editor": {},
            }
            
        elif next_method == "Switch":
            if rag_match and isinstance(rag_match.get("test_data"), dict):
                test_data = rag_match["test_data"]
            else:
                test_data = {
                    "editor": {
                        "FLD_CSTM": {
                            "Spatial Context": "Stationsschema"
                        }
                    }
                }
        elif self._is_ui_or_navigation_method(next_method):
            if rag_match and isinstance(rag_match.get("test_data"), dict):
                test_data = rag_match["test_data"]
            else:
                test_data = self._generate_navigation_test_data(
                    next_obj,
                    next_method,
                    prev_id,
                )

        step_data = {
            "step_index": step_index,
            "database": self._database_for_method(next_method, next_obj),
            "object": next_obj,
            "object_id": self._object_id_for_method(next_method, next_id, prev_id),
            "module": self._module_for_method(next_method),
            "method": "Open Object" if next_method == "Open" else next_method,
            "command": self._command_for_method(next_method),
            "test_data": test_data,
            "_rag_sourced": bool(rag_match),
            "_matched_instruction": rag_match.get("instruction", "") if rag_match else ""
        }
        
        self.steps.append(step_data)
        return step_data

    def _generate_test_data_body(self, obj: str, method: str, obj_id: str) -> Dict[str, Any]:
        """Build the test_data body for a single-step instruction."""
        if method == "Create":
            return {
                "create": {
                    "Object": obj,
                    "Type": "Create",
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM0_0": {
                        "ID": obj_id,
                    },
                },
                "update": {},
                "editor": {},
            }
        elif method == "Update":
            return {
                "create": {},
                "update": {
                    "Object": obj,
                    "Type": "Update",
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM0_0": {
                        "ID": obj_id,
                    },
                },
                "editor": {},
            }
        elif method == "Delete":
            return {
                "create": {},
                "update": {},
                "editor": {},
            }
        elif method == "Open":
            return {
                "create": {
                },
                "update": {},
                "editor": {
                    "Object": obj,
                    "Type": "Open Object",
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM0_0": {
                        "Spatial Context": "Stationsschema",
                        "Station Nummer": self.current_station,
                        "ID": obj_id,
                    },
                },
            }
        return {}

    @staticmethod
    def _is_ui_or_navigation_method(method: str) -> bool:
        return method in {
            "Click Oneshot Button",
            "Datamodel Check",
            "Select Tab",
            "Select first HV object",
            "Select second HV object",
            "Switch Spatial Context",
            "Verify Field",
        }

    def _generate_navigation_test_data(
        self,
        obj: str,
        method: str,
        obj_id: str,
    ) -> Dict[str, Any]:
        if method in {"Click Oneshot Button", "Select Tab", "Datamodel Check"}:
            return {"create": {}, "update": {}, "editor": {}}

        if method in {"Select first HV object", "Select second HV object"}:
            position = "first" if "first" in method else "second"
            return {
                "create": {},
                "update": {},
                "editor": {
                    "Object": obj,
                    "Type": method,
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM": {
                        "Object": f":{obj.lower().replace(' ', '_')}",
                        "ID_HV": "None",
                        "Position": position,
                        "ID": obj_id,
                    },
                },
            }

        if method == "Switch Spatial Context":
            return {
                "create": {},
                "update": {},
                "editor": {
                    "Object": obj,
                    "Type": method,
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM": {
                        "Spatial Context": "Stationsschema",
                        "Station Nummer": self.current_station,
                        "ID": obj_id,
                    },
                },
            }

        if method == "Verify Field":
            return {
                "create": {},
                "update": {},
                "editor": {
                    "Object": obj,
                    "Type": method,
                    "Dataset": self.database,
                    "Custom": "Yes",
                    "FLD_CSTM": {
                        "Field": "Status",
                        "Expected": "In Bedrijf",
                        "ID": obj_id,
                    },
                },
            }

        return {}

    def _database_for_method(self, method: str, obj: str) -> str:
        if obj == "Stationsschema":
            return ""
        if method in {"Click Oneshot Button", "Select Tab"}:
            return ":algemeen"
        return self.database

    @staticmethod
    def _object_id_for_method(method: str, next_id: str, prev_id: str) -> str:
        if method == "Create":
            return next_id
        if method in {
            "Click Oneshot Button",
            "Datamodel Check",
            "Select Tab",
            "Select first HV object",
            "Select second HV object",
            "Switch Spatial Context",
            "Verify Field",
        }:
            return "Passed"
        return prev_id

    @staticmethod
    def _module_for_method(method: str) -> str:
        if method in ["Create", "Update", "Delete"]:
            return "Datamodel CRUD"
        if method == "Click Oneshot Button":
            return "Buttons"
        if method == "Select Tab":
            return "Tabs"
        if method in {"Select first HV object", "Select second HV object"}:
            return "Hierarchy Viewer"
        if method == "Datamodel Check":
            return "Datamodel Consistency Check"
        return "Editor(s)"

    @staticmethod
    def _command_for_method(method: str) -> str:
        if method in ["Create", "Update", "Delete"]:
            return "Execute Datamodel CRUD Testcommand"
        if method == "Click Oneshot Button":
            return "Execute Buttons Testcommand"
        if method == "Select Tab":
            return "Execute Tabs Testcommand"
        if method in {"Select first HV object", "Select second HV object"}:
            return "Execute Hierarchy Viewer Testcommand"
        if method == "Datamodel Check":
            return "Execute Datamodel Check Testcommand"
        return "Execute Object Control Testcommand"

    def get_full_workflow_json(self) -> str:
        """Return the assembled multi-step workflow as a runnable JSON document."""
        workflow_data = {
            "file_id": f"file_scaffolded_{str(uuid.uuid4())[:8]}",
            "test_env": "TST",
            "test_app": "NRG Beheerkaart Elektra MS",
            "total_steps": len(self.steps),
            "steps": self.steps
        }
        return json.dumps(workflow_data, indent=4, ensure_ascii=False)
