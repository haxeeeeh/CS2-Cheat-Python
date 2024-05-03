import asyncio
import json
import multiprocessing
import os
import time
import tkinter as tk
from tkinter import ttk
from json import JSONDecodeError
import re
import keyboard
import pyautogui
import pyfiglet
import pyMeow as pw_module
import requests
from pynput.mouse import Button, Controller
from win32gui import GetForegroundWindow, GetWindowText
from fernet import Fernet
from tkinter.font import Font


class ConfigEditor:
    def __init__(self, master, config, program):
        self.master = master
        self.config = config
        self.program = program
        self.create_widgets()

    def create_widgets(self):
        self.checkboxes = {}
        self.inputs = {}

        for i, (key, value) in enumerate(self.config.items()):
            label = ttk.Label(self.master, text=key)
            label.grid(row=i, column=0, sticky="w")

            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                checkbox = ttk.Checkbutton(self.master, text=key, variable=var, command=lambda key=key: self.update_config(key))
                checkbox.grid(row=i, column=1, sticky="w")
                self.checkboxes[key] = var
                checkbox.bind("<ButtonRelease-1>", lambda event, key=key: self.update_config(key))
            elif key == "triggerKey":
                dropdown_var = tk.StringVar(value=value)
                dropdown = ttk.Combobox(self.master, textvariable=dropdown_var, values=["shift", "ctrl", "alt", "spacebar"], state="readonly")
                dropdown.grid(row=i, column=1, sticky="we")
                dropdown.bind("<<ComboboxSelected>>", lambda event, key=key, var=dropdown_var: self.update_config_dropdown(key, var))
                self.inputs[key] = dropdown_var
            elif key in ["CrosshairSize"]:
                continue
            elif key == "HeadShape":  # Add this condition
                dropdown_var = tk.StringVar(value=value)
                dropdown = ttk.Combobox(self.master, textvariable=dropdown_var, values=["Square", "Circle"], state="readonly")
                dropdown.grid(row=i, column=1, sticky="we")
                dropdown.bind("<<ComboboxSelected>>", lambda event, key=key, var=dropdown_var: self.update_config_dropdown(key, var))
                self.inputs[key] = dropdown_var
            elif key in ["HealthEspFontSize", "NameEspFontSize"]:  # Adding font size adjustments
                entry_var = tk.IntVar(value=value)
                entry = ttk.Entry(self.master, textvariable=entry_var)
                entry.grid(row=i, column=1, sticky="we")
                entry.bind("<Return>", lambda event, key=key: self.update_config(key))
                self.inputs[key] = entry_var
            else:
                entry_var = tk.StringVar(value=str(value))
                entry = ttk.Entry(self.master, textvariable=entry_var)
                entry.grid(row=i, column=1, sticky="we")
                entry.bind("<Return>", lambda event, key=key: self.update_config(key))
                self.inputs[key] = entry_var

    def update_config_dropdown(self, key, dropdown_var):
        self.config[key] = dropdown_var.get()
        self.program.apply_config(self.config)
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)

    def update_config(self, key):
        if key in self.checkboxes:
            self.config[key] = self.checkboxes[key].get()
        elif key in self.inputs:
            self.config[key] = self.inputs[key].get()

        self.program.apply_config(self.config)
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)


class Offsets:
    try:
        with open("offsets.json", "r") as f:
            offset_data = json.load(f)

        with open("client.dll.cs", "r") as f:
            client_data = f.read()

        # Verify if client.dll data is available
        if "client.dll" not in offset_data or "client.dll" not in client_data:
            raise Exception("Offset data for client.dll not found in the fetched JSON.")

        # Parse offset data from JSON
        dwEntityList = offset_data["client.dll"].get("dwEntityList")
        dwViewMatrix = offset_data["client.dll"].get("dwViewMatrix")
        dwLocalPlayerPawn = offset_data["client.dll"].get("dwLocalPlayerPawn")

        # Parse member offsets from client.dll.cs text
        member_offsets = {
            "m_iszPlayerName": "int32",
            "m_iHealth": "int32",
            "m_iTeamNum": "int32",
            "m_vOldOrigin": "Vector",
            "m_pGameSceneNode": "int32",
            "m_hPlayerPawn": "int32",
            "m_iIDEntIndex": "int32"
        }

        for member, data_type in member_offsets.items():
            match = re.search(f"{member}\s+=\s+(\w+)", client_data)
            if match:
                offset_hex = match.group(1)
                offset_int = int(offset_hex, 16)
                locals()[member] = offset_int
            else:
                raise Exception(f"Offset for {member} not found in client.dll.cs")

        # Verify if any offsets are missing
        if any(offset is None for offset in [dwEntityList, dwViewMatrix, dwLocalPlayerPawn, m_iszPlayerName, m_iHealth, m_iTeamNum, m_vOldOrigin, m_pGameSceneNode, m_hPlayerPawn, m_iIDEntIndex]):
            raise Exception("One or more required offsets are missing.")

    except Exception as e:
        exit(f"Error: {e}")


class Entity:
    # Define bone names mapping to their indices
    BONE_NAMES = {
        0: "pelvis",
        2: "spine_2",
        4: "spine_1",
        5: "neck_0",
        6: "head",
        8: "arm_upper_L",
        9: "arm_lower_L",
        13: "arm_upper_R",
        14: "arm_lower_R",
        15: "hand_R",
        20: "hand_L",
        22: "leg_upper_L",
        23: "leg_lower_L",
        24: "ankle_L",
        25: "leg_upper_R",
        26: "leg_lower_R",
        27: "ankle_R",
    }

    # Define bone connections for drawing skeleton
    BONE_CONNECTIONS = [
        (0, 2),
        (2, 4),
        (4, 5),
        (5, 6),
        (4, 8),
        (8, 9),
        (9, 10),  # New connection for left hand
        (4, 13),
        (13, 14),
        (14, 15),
        (0, 22),
        (22, 23),
        (23, 24),
        (0, 25),
        (25, 26),
        (26, 27)
    ]
    
    def __init__(self, pointer, pawnPointer, process):
        self.pointer = pointer
        self.pawnPointer = pawnPointer
        self.process = process
        self.pos2d = None
        self.headPos2d = None

    def Health(self):
        return pw_module.r_int(self.process, self.pawnPointer + Offsets.m_iHealth)

    def Team(self):
        return pw_module.r_int(self.process, self.pawnPointer + Offsets.m_iTeamNum)

    def Pos(self):
        return pw_module.r_vec3(self.process, self.pawnPointer + Offsets.m_vOldOrigin)

    def BonePos(self, bone_index):
        gameScene = pw_module.r_int64(self.process, self.pawnPointer + Offsets.m_pGameSceneNode)
        boneArrayPointer = pw_module.r_int64(self.process, gameScene + 480)
        bone_position = pw_module.r_vec3(self.process, boneArrayPointer + bone_index * 32)
        return bone_position

    def Wts(self, matrix):
        try:
            self.pos2d = pw_module.world_to_screen(matrix, self.Pos(), 1)
            self.headPos2d = pw_module.world_to_screen(matrix, self.BonePos(6), 1)  # Defaulting to head bone (index 6)
        except:
            return False
        
        return True



    def draw_circle_bones(self, matrix, color):
        screen_width, screen_height = pyautogui.size()
        
        # Define the bone indices for the bones to draw circles over
        bone_indices = [6, 15, 10, 2, 23, 26]  # Indices for hand_R, hand_L, leg_upper_L, leg_upper_R, head
        
        for bone_index in bone_indices:
            bone_pos = self.BonePos(bone_index)
            
            try:
                bone_pos_screen = pw_module.world_to_screen(matrix, bone_pos, 1)
            except Exception as e:
                continue
            
            # Check if the bone position is within the screen boundaries
            if bone_pos_screen:
                bone_x, bone_y = bone_pos_screen["x"], bone_pos_screen["y"]
                
                # Perform boundary checks
                if 0 <= bone_x < screen_width and 0 <= bone_y < screen_height:
                    pw_module.draw_circle_lines(bone_x, bone_y, 5, pw_module.get_color(color))

    def draw_skeleton(self, matrix, color):
        screen_width, screen_height = pyautogui.size()
        
        for bone_start, bone_end in self.BONE_CONNECTIONS:
            start_pos = self.BonePos(bone_start)
            end_pos = self.BonePos(bone_end)
            
            try:
                start_pos_screen = pw_module.world_to_screen(matrix, start_pos, 1)
                end_pos_screen = pw_module.world_to_screen(matrix, end_pos, 1)
            except Exception as e:
                continue
            
            # Check if both start and end positions are within the screen boundaries
            if start_pos_screen and end_pos_screen:
                start_x, start_y = start_pos_screen["x"], start_pos_screen["y"]
                end_x, end_y = end_pos_screen["x"], end_pos_screen["y"]
                
                # Perform boundary checks
                if 0 <= start_x < screen_width and 0 <= start_y < screen_height and 0 <= end_x < screen_width and 0 <= end_y < screen_height:
                    pw_module.draw_line(start_x, start_y, end_x, end_y, pw_module.get_color(color))


class WallHack:
    def __init__(self, process, module, config):  
        self.process = process
        self.module = module
        self.config = config  

    def GetEntities(self):
        entityList = pw_module.r_int64(self.process, self.module + Offsets.dwEntityList)
        localPlayer = pw_module.r_int64(self.process, self.module + Offsets.dwLocalPlayerPawn)
        localPlayerTeam = pw_module.r_int(self.process, localPlayer + Offsets.m_iTeamNum)

        for _ in range(1, 65):
            try:
                entryPointer = pw_module.r_int64(self.process, entityList + (8 * (_ & 0x7FFF) >> 9) + 16)
                controllerPointer = pw_module.r_int64(self.process, entryPointer + 120 * (_ & 0x1FF))

                if controllerPointer == localPlayer:
                    continue

                controllerPawnPointer = pw_module.r_int64(self.process, controllerPointer + Offsets.m_hPlayerPawn)
                listEntityPointer = pw_module.r_int64(self.process, entityList + 0x8 * ((controllerPawnPointer & 0x7FFF) >> 9) + 16)
                pawnPointer = pw_module.r_int64(self.process, listEntityPointer + 120 * (controllerPawnPointer & 0x1FF))
            except:
                continue

            entity_team = pw_module.r_int(self.process, pawnPointer + Offsets.m_iTeamNum)
            if not self.config["TeamEsp"] and entity_team == localPlayerTeam:
                continue

            yield Entity(controllerPointer, pawnPointer, self.process)
            
    def Render(self):
        matrix = pw_module.r_floats(self.process, self.module + Offsets.dwViewMatrix, 16)
        
        for entity in self.GetEntities():
            if entity.Wts(matrix) and entity.Health() > 0:
                head = entity.pos2d["y"] - entity.headPos2d["y"]
                width = head / 2
                center = width / 2
                color = pw_module.get_color(self.config["BoxColor"]) if entity.Team() != 2 else pw_module.get_color(self.config["BoxEnemyColor"])
                fill = pw_module.fade_color(pw_module.get_color(self.config["BackgroundBox"]), 0.5)

                if self.config["BoxEsp"]:
                    pw_module.draw_rectangle(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, fill)
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, color, 1)

                if self.config["DrawHealthBar"]:
                    health_bar_width = 5
                    health_bar_max_height = head
                    health_bar_color = pw_module.get_color("green") if entity.Health() > 50 else pw_module.get_color("yellow") if entity.Health() > 20 else pw_module.get_color("red")
                    
                    health_percentage = entity.Health() / 100
                    health_bar_height = health_bar_max_height * health_percentage
                    
                    health_bar_x = entity.headPos2d["x"] - center - health_bar_width - 2 
                    health_bar_y = entity.headPos2d["y"] - center / 2 + (health_bar_max_height - health_bar_height)  

                    health_bar_border_x = health_bar_x - 1  
                    health_bar_border_y = entity.headPos2d["y"] - center / 2 - 1  

                    pw_module.draw_rectangle(health_bar_border_x, health_bar_border_y, health_bar_width + 2, health_bar_max_height + 2, pw_module.get_color("black"))

                    pw_module.draw_rectangle(health_bar_x, health_bar_y, health_bar_width, health_bar_height, health_bar_color)

                if self.config["LineEsp"]:
                    screen_center_x, screen_height = pyautogui.size()
                    pw_module.draw_line(screen_center_x / 2, screen_height, entity.headPos2d["x"], entity.headPos2d["y"], pw_module.get_color(self.config["LineColor"]))

                if self.config["HeadEsp"]:
                    head_size = 10  
                    head_color = pw_module.get_color(self.config["HeadColor"])
                    if self.config["HeadShape"] == "Square":
                        pw_module.draw_rectangle_lines(entity.headPos2d["x"] - head_size / 2, entity.headPos2d["y"] - head_size / 2, head_size, head_size, head_color, 1)
                    elif self.config["HeadShape"] == "Circle":
                        pw_module.draw_circle_lines(entity.headPos2d["x"], entity.headPos2d["y"], head_size / 2, head_color)

                if self.config["HealthEsp"]:
                    health_text = f"Health: {entity.Health()}"
                    pw_module.draw_text(health_text, entity.headPos2d["x"] + center + 5, entity.headPos2d["y"] - center / 2, self.config["HealthEspFontSize"], pw_module.get_color("white"))

                if self.config["NameEsp"]:
                    player_name = pw_module.r_string(self.process, entity.pointer + Offsets.m_iszPlayerName)
                    name_width = pw_module.measure_text(player_name, self.config["NameEspFontSize"])  
                    pw_module.draw_text(player_name, entity.headPos2d["x"] - name_width / 2, entity.headPos2d["y"] - center - 10, self.config["NameEspFontSize"], pw_module.get_color("white"))
                
                if self.config["SkeletonEsp"]:  
                    entity.draw_skeleton(matrix, self.config["SkeletonColor"])

                if self.config.get("CircleBoneEsp", False):  
                    entity.draw_circle_bones(matrix, self.config["CircleBoneColor"])  

        
        time.sleep(0.01)
        
        pw_module.end_drawing()

    def RenderWatermark(self):
        if not self.config["WaterMark"]:
            return
        
        watermark_text = "GHax"
        made_by_text = "Made by Cr0mb"
        
        watermark_color = pw_module.get_color("white")
        watermark_background = pw_module.get_color("black")
        
        watermark_text_width = pw_module.measure_text(watermark_text, 24)
        made_by_text_width = pw_module.measure_text(made_by_text, 12)
        
        background_width = max(watermark_text_width, made_by_text_width) + 20
        background_height = 64
        
        watermark_x = 10
        watermark_y = 10
        made_by_y = watermark_y + 34
        
        pw_module.draw_rectangle(watermark_x, watermark_y, background_width, background_height, watermark_background)
        
        pw_module.draw_text(watermark_text, watermark_x + 10, watermark_y + 5, 24, watermark_color)
        
        pw_module.draw_text(made_by_text, watermark_x + 10, made_by_y, 12, watermark_color)

    def RenderCrosshair(self):
        if not self.config["Crosshair"]:
            return
        
        crosshair_text = "+"
        crosshair_color = pw_module.get_color("white")
        
        screen_center_x, screen_center_y = pyautogui.size()
        crosshair_x = (screen_center_x - 20) / 2 + 4 
        crosshair_y = (screen_center_y - 20) / 2  
        
        pw_module.draw_text(crosshair_text, crosshair_x, crosshair_y, 20, crosshair_color)


class Program:
    def __init__(self):
        try:
            self.window = "Counter-Strike 2"
            self.fps = 60
            self.config = self.load_config()
            self.process = pw_module.open_process("cs2.exe")
            self.module = pw_module.get_module(self.process, "client.dll")["base"]
            self.wall = WallHack(self.process, self.module, self.config)  
            self.triggerbot_enabled = self.config.get("Triggerbot", False)
            self.trigger_key = self.config.get("triggerKey", "shift")
            self.triggerbot_on_same_team = self.config.get("triggerbotOnSameTeam", False)
        except:
            exit("Error: Enable only after opening Counter Strike 2")

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            print("Config file not found.")
            return {}
        except JSONDecodeError:
            print("Error when parsing JSON data from the config file.")
            return {}


    def apply_config(self, new_config):
        self.config = new_config
        self.wall.config = new_config  

        self.triggerbot_enabled = self.config.get("Triggerbot", False)
        self.trigger_key = self.config.get("triggerKey", "shift")
        self.triggerbot_on_same_team = self.config.get("triggerbotOnSameTeam", False)  

    async def run(self):
        pw_module.overlay_init(target=self.window, title=self.window, fps=self.fps)

        while pw_module.overlay_loop():
            try:
                self.config = self.load_config()  
                self.apply_config(self.config)

                if self.config["BoxEsp"] or self.config["LineEsp"] or self.config["HeadEsp"] or self.config["DrawHealthBar"] or self.config["NameEsp"]:
                    self.wall.Render()

                if self.config.get("WaterMark", False):
                    self.wall.RenderWatermark()

                if self.config["Crosshair"]:
                    self.wall.RenderCrosshair()

                if self.triggerbot_enabled and GetWindowText(GetForegroundWindow()) == "Counter-Strike 2" and keyboard.is_pressed(self.trigger_key):
                    self.triggerbot()

            except Exception as e:
                print(f"Error in main loop: {e}")

    def triggerbot(self):
        player = pw_module.r_int64(self.process, self.module + Offsets.dwLocalPlayerPawn)
        entityId = pw_module.r_int(self.process, player + Offsets.m_iIDEntIndex)

        if entityId > 0:
            entList = pw_module.r_int64(self.process, self.module + Offsets.dwEntityList)

            entEntry = pw_module.r_int64(self.process, entList + 0x8 * (entityId >> 9) + 0x10)
            entity = pw_module.r_int64(self.process, entEntry + 120 * (entityId & 0x1FF))

            entityTeam = pw_module.r_int(self.process, entity + Offsets.m_iTeamNum)
            entityHp = pw_module.r_int(self.process, entity + Offsets.m_iHealth)

            playerTeam = pw_module.r_int(self.process, player + Offsets.m_iTeamNum)

            if entityHp > 0 and (self.triggerbot_on_same_team or entityTeam != playerTeam):  
                delay = 0.01  
                time.sleep(delay)
                mouse = Controller()
                mouse.click(Button.left)


def main():
    program = Program()
    process = multiprocessing.Process(target=run_tkinter, args=(program,))
    process.start()
    asyncio.run(program.run())
    process.join()

def run_tkinter(program):
    root = tk.Tk()
    root.title("Config Editor")
    editor = ConfigEditor(root, program.config, program)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.Process(target=main).start()
