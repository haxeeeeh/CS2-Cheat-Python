import tkinter as tk
from tkinter import ttk
from json import load, dump
import asyncio
import os
import multiprocessing
import keyboard
import time
from pynput.mouse import Controller, Button
from win32gui import GetWindowText, GetForegroundWindow
import pyautogui
import requests
import pyMeow as pw_module
from fernet import Fernet
import pyfiglet

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
            elif key == "CrosshairSize":  
                continue
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
            dump(self.config, f, indent=4)

    def update_config(self, key):
        if key in self.checkboxes:
            self.config[key] = self.checkboxes[key].get()
        elif key in self.inputs:
            self.config[key] = self.inputs[key].get()

        self.program.apply_config(self.config)
        with open("config.json", "w") as f:
            dump(self.config, f, indent=4)

class Offsets:
    try:
        offset = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json").json()
        client = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client.dll.json").json()

        dwEntityList = offset["client.dll"]["dwEntityList"]
        dwViewMatrix = offset["client.dll"]["dwViewMatrix"]
        dwLocalPlayerPawn = offset["client.dll"]["dwLocalPlayerPawn"]
        m_iszPlayerName = client["client.dll"]["classes"]["CBasePlayerController"]["fields"]["m_iszPlayerName"]
        m_iHealth = client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_iHealth"]
        m_iTeamNum = client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_iTeamNum"]
        m_vOldOrigin = client["client.dll"]["classes"]["C_BasePlayerPawn"]["fields"]["m_vOldOrigin"]
        m_pGameSceneNode = client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_pGameSceneNode"]
        m_hPlayerPawn = client["client.dll"]["classes"]["CCSPlayerController"]["fields"]["m_hPlayerPawn"]
        m_iIDEntIndex = client["client.dll"]["classes"]["C_CSPlayerPawnBase"]["fields"]["m_iIDEntIndex"]
    except:
        exit("Error: Invalid offsets, wait for an update")

class Entity:
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

    def BonePos(self, bone):
        gameScene = pw_module.r_int64(self.process, self.pawnPointer + Offsets.m_pGameSceneNode)
        boneArrayPointer = pw_module.r_int64(self.process, gameScene + 480)
        return pw_module.r_vec3(self.process, boneArrayPointer + bone * 32)

    def Wts(self, matrix):
        try:
            self.pos2d = pw_module.world_to_screen(matrix, self.Pos(), 1)
            self.headPos2d = pw_module.world_to_screen(matrix, self.BonePos(6), 1)
        except:
            return False
        
        return True
        
class WallHack:
    def __init__(self, process, module, teamEsp=True, drawHealthBar=True, lineEsp=True, headEsp=True, boxEsp=True, boxColor="red", boxEnemyColor="blue", lineColor="white", headColor="white", backgroundColor="black", healthEsp=True, nameEsp=True, watermark=True, crosshair=True):
        self.process = process
        self.module = module
        self.teamEsp = teamEsp
        self.drawHealthBar = drawHealthBar
        self.lineEsp = lineEsp
        self.headEsp = headEsp
        self.boxEsp = boxEsp
        self.boxColor = boxColor
        self.boxEnemyColor = boxEnemyColor
        self.lineColor = lineColor
        self.headColor = headColor
        self.backgroundColor = backgroundColor
        self.healthEsp = healthEsp
        self.nameEsp = nameEsp
        self.watermark = watermark
        self.crosshair = crosshair

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
            if not self.teamEsp and entity_team == localPlayerTeam:
                continue

            yield Entity(controllerPointer, pawnPointer, self.process)
            
    def Render(self):
        matrix = pw_module.r_floats(self.process, self.module + Offsets.dwViewMatrix, 16)
        
        for entity in self.GetEntities():
            if entity.Wts(matrix) and entity.Health() > 0:
                head = entity.pos2d["y"] - entity.headPos2d["y"]
                width = head / 2
                center = width / 2
                color = pw_module.get_color(self.boxColor) if entity.Team() != 2 else pw_module.get_color(self.boxEnemyColor)
                fill = pw_module.fade_color(pw_module.get_color(self.backgroundColor), 0.5)

                if self.boxEsp:
                    pw_module.draw_rectangle(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, fill)
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, color, 1)

                if self.drawHealthBar:
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

                if self.lineEsp:
                    screen_center_x, screen_height = pyautogui.size()
                    pw_module.draw_line(screen_center_x / 2, screen_height, entity.headPos2d["x"], entity.headPos2d["y"], pw_module.get_color(self.lineColor))

                if self.headEsp:
                    head_size = 10  
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - head_size / 2, entity.headPos2d["y"] - head_size / 2, head_size, head_size, pw_module.get_color(self.headColor), 1)

                if self.healthEsp:
                    health_text = f"Health: {entity.Health()}"
                    pw_module.draw_text(health_text, entity.headPos2d["x"] + center + 5, entity.headPos2d["y"] - center / 2, 12, pw_module.get_color("white"))

                if self.nameEsp:
                    player_name = pw_module.r_string(self.process, entity.pointer + Offsets.m_iszPlayerName)
                    name_width = pw_module.measure_text(player_name, 12)  
                    pw_module.draw_text(player_name, entity.headPos2d["x"] - name_width / 2, entity.headPos2d["y"] - center - 10, 12, pw_module.get_color("white"))

        pw_module.end_drawing()

    def RenderWatermark(self):
        if not self.watermark:
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
        if not self.crosshair:
            return
        
        crosshair_text = "+"
        crosshair_color = pw_module.get_color("white")
        
        screen_center_x, screen_center_y = pyautogui.size()
        crosshair_x = (screen_center_x - 20) / 2 + 4 # Center the crosshair horizontally
        crosshair_y = (screen_center_y - 20) / 2  # Center the crosshair vertically
        
        pw_module.draw_text(crosshair_text, crosshair_x, crosshair_y, 20, crosshair_color)

class Program:
    def __init__(self):
        try:
            self.window = "Counter-Strike 2"
            self.fps = 144
            self.config = self.load_config()
            self.process = pw_module.open_process("cs2.exe")
            self.module = pw_module.get_module(self.process, "client.dll")["base"]
            self.wall = WallHack(
                self.process, 
                self.module, 
                teamEsp=self.config["TeamEsp"], 
                drawHealthBar=self.config["DrawHealthBar"],
                lineEsp=self.config["LineEsp"],
                headEsp=self.config["HeadEsp"],
                boxEsp=self.config["BoxEsp"],
                boxColor=self.config["BoxColor"],
                boxEnemyColor=self.config["BoxEnemyColor"],
                lineColor=self.config["LineColor"],
                headColor=self.config["HeadColor"],
                backgroundColor=self.config["BackgroundBox"],
                healthEsp=self.config["HealthEsp"],
                nameEsp=self.config["NameEsp"],
                watermark=self.config["WaterMark"],
                crosshair=self.config["Crosshair"],
            )  

            self.triggerbot_enabled = self.config.get("Triggerbot", False)
            self.trigger_key = self.config.get("triggerKey", "shift")
            self.triggerbot_on_same_team = self.config.get("triggerbotOnSameTeam", False)
        except:
            exit("Error: Enable only after opening Counter Strike 2")

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as file:
                return load(file)
        except FileNotFoundError:
            print("Config file not found.")
            return {}
        except JSONDecodeError:
            print("Error when parsing JSON data from the config file.")
            return {}


    def apply_config(self, new_config):
        self.config = new_config
        self.wall.teamEsp = self.config["TeamEsp"]
        self.wall.drawHealthBar = self.config["DrawHealthBar"]
        self.wall.lineEsp = self.config["LineEsp"]
        self.wall.headEsp = self.config["HeadEsp"]
        self.wall.boxEsp = self.config["BoxEsp"]
        self.wall.boxColor = self.config["BoxColor"]
        self.wall.boxEnemyColor = self.config["BoxEnemyColor"]
        self.wall.lineColor = self.config["LineColor"]
        self.wall.headColor = self.config["HeadColor"]
        self.wall.backgroundColor = self.config["BackgroundBox"]
        self.wall.healthEsp = self.config["HealthEsp"]
        self.wall.nameEsp = self.config["NameEsp"]
        self.wall.watermark = self.config["WaterMark"]

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
                print(f"Error: {e}")
                pass

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
    root = tk.Tk()
    root.title("GHax")
    try:
        with open("config.json", "r") as f:
            config = load(f)
    except FileNotFoundError:
        config = {
            "BoxEsp": True,
            "BoxColor": "red",
            "BoxEnemyColor": "blue",
            "BackgroundBox": "black",
            "DrawHealthBar": True,
            "LineEsp": False,
            "LineColor": "white",
            "HeadEsp": False,
            "HeadColor": "purple",
            "TeamEsp": True,
            "Triggerbot": False,
            "triggerKey": "shift",
            "triggerbotOnSameTeam": False,  
            "HealthEsp": True,  
            "NameEsp": True,  
            "WaterMark": True,
            "Crosshair": True,
        }
    
    # Print "GHax Client" in large text
    print(pyfiglet.figlet_format("GHax Client"))

    # Print "Made by Cr0mb" in smaller text
    print("Made by Cr0mb")

    program = Program()
    editor = ConfigEditor(root, config, program)
    root.mainloop()

if __name__ == "__main__":
    multiprocessing.Process(target=main).start()
    program = Program()
    asyncio.run(program.run())
