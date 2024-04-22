import tkinter as tk
from tkinter import ttk
from json import load, dump
import asyncio
import os
from importlib import import_module
import multiprocessing
from random import uniform

# Dynamic imports
pw_module = import_module('py' + 'Meow')
pymem = import_module('py' + 'mem')
pynput = import_module('pyn' + 'put')
pyautogui = import_module('pyau' + 'togui')
requests = import_module('re' + 'quests')

class ConfigEditor:
    def __init__(self, master, config):
        self.master = master
        self.config = config
        self.create_widgets()

    def create_widgets(self):
        self.checkboxes = {}
        self.inputs = {}

        for i, (key, value) in enumerate(self.config.items()):
            if isinstance(value, bool):
                var = tk.BooleanVar(value=self.config[key])
                checkbox = ttk.Checkbutton(self.master, text=key, variable=var)
                checkbox.grid(row=i, column=0, sticky="w")
                self.checkboxes[key] = var
            else:
                label = ttk.Label(self.master, text=key)
                label.grid(row=i, column=0, sticky="w")
                entry_var = tk.StringVar()
                entry_var.set(value)
                entry = ttk.Entry(self.master, textvariable=entry_var)
                entry.grid(row=i, column=1, sticky="we")
                self.inputs[key] = entry_var

        apply_button = ttk.Button(self.master, text="Apply", command=self.apply_changes)
        apply_button.grid(row=len(self.config), columnspan=2, sticky="we")

    def apply_changes(self):
        for key, var in self.checkboxes.items():
            self.config[key] = var.get()

        for key, var in self.inputs.items():
            self.config[key] = var.get()

        with open("config.json", "w") as f:
            dump(self.config, f, indent=4)

class Offsets:
    try:
        offset = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json").json()
        client = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client.dll.json").json()

        dwEntityList = offset["client.dll"]["dwEntityList"]
        dwViewMatrix = offset["client.dll"]["dwViewMatrix"]
        dwLocalPlayerPawn = offset["client.dll"]["dwLocalPlayerPawn"]
        dwLocalPlayerController = offset["client.dll"]["dwLocalPlayerController"]
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
    def __init__(self, process, module, teamEsp=True, drawHealthBar=True, lineEsp=True, headEsp=True, boxEsp=True, boxColor="red", boxEnemyColor="blue", lineColor="white", headColor="white", backgroundColor="black"):
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

    def GetEntities(self):
        entityList = pw_module.r_int64(self.process, self.module + Offsets.dwEntityList)
        localPlayer = pw_module.r_int64(self.process, self.module + Offsets.dwLocalPlayerController)
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
                    # Fill
                    pw_module.draw_rectangle(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, fill)

                    # Box with black border
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, color, 1)

                if self.drawHealthBar:
                    # Health Bar
                    health_bar_width = 5  # Width of the health bar
                    health_bar_max_height = head  # Maximum height of the health bar, same as the box
                    health_bar_color = pw_module.get_color("green") if entity.Health() > 50 else pw_module.get_color("yellow") if entity.Health() > 20 else pw_module.get_color("red")
                    
                    # Calculate the height of the health bar based on player's health percentage
                    health_percentage = entity.Health() / 100
                    health_bar_height = health_bar_max_height * health_percentage
                    
                    # Calculate the position of the health bar
                    health_bar_x = entity.headPos2d["x"] - center - health_bar_width - 2  # Adjusting for spacing
                    health_bar_y = entity.headPos2d["y"] - center / 2 + (health_bar_max_height - health_bar_height)  # Adjusting for top border

                    # Draw black border around health bar (fixed position)
                    # Calculate the position of the health bar border
                    health_bar_border_x = health_bar_x - 1  # Adjusting for left border
                    health_bar_border_y = entity.headPos2d["y"] - center / 2 - 1  # Adjusting for top border

                    pw_module.draw_rectangle(health_bar_border_x, health_bar_border_y, health_bar_width + 2, health_bar_max_height + 2, pw_module.get_color("black"))

                    # Draw colored portion of health bar (dynamically updating)
                    pw_module.draw_rectangle(health_bar_x, health_bar_y, health_bar_width, health_bar_height, health_bar_color)

                if self.lineEsp:
                    # Draw line from bottom center of screen to player's head position
                    screen_center_x, screen_height = pyautogui.size()
                    pw_module.draw_line(screen_center_x / 2, screen_height, entity.headPos2d["x"], entity.headPos2d["y"], pw_module.get_color(self.lineColor))

                if self.headEsp:
                    # Draw a box around player's head
                    head_size = 10  # Size of the head box
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - head_size / 2, entity.headPos2d["y"] - head_size / 2, head_size, head_size, pw_module.get_color(self.headColor), 1)

        pw_module.end_drawing()

class TriggerBot:
    def __init__(self, ignoreTeam=False):
        self.ignoreTeam = ignoreTeam
        self.mouse = pynput.mouse.Controller()
        self.pm = pymem.Pymem("cs2.exe")
        self.client = pymem.process.module_from_name(self.pm.process_handle, "client.dll").lpBaseOfDll
        self.trigger_enabled = False  # Initialize triggerbot state
        self.key_pressed = False

    async def EnableAsync(self):
        player = self.pm.read_longlong(self.client + Offsets.dwLocalPlayerPawn)
        entityId = self.pm.read_int(player + Offsets.m_iIDEntIndex)

        if entityId > 0:
            entList = self.pm.read_longlong(self.client + Offsets.dwEntityList)
            entEntry = self.pm.read_longlong(entList + 0x8 * (entityId >> 9) + 0x10)
            entity = self.pm.read_longlong(entEntry + 120 * (entityId & 0x1FF))
            entityTeam = self.pm.read_int(entity + Offsets.m_iTeamNum)
            playerTeam = self.pm.read_int(player + Offsets.m_iTeamNum)
            entityHp = self.pm.read_int(entity + Offsets.m_iHealth)

            if self.ignoreTeam or (entityTeam != playerTeam) and entityHp > 0:
                await self.ShootAsync()

    async def ShootAsync(self):
        await asyncio.sleep(uniform(0.01, 0.03))
        self.mouse.press(pynput.mouse.Button.left)
        await asyncio.sleep(uniform(0.01, 0.05))
        self.mouse.release(pynput.mouse.Button.left)
        await asyncio.sleep(0.1)

    def on_press(self, key):
        if key == pynput.keyboard.Key.alt_l:
            self.key_pressed = True
            self.trigger_enabled = True

    def on_release(self, key):
        if key == pynput.keyboard.Key.alt_l:
            self.key_pressed = False
            self.trigger_enabled = False

class Program:
    def __init__(self):
        try:
            self.window = "Counter-Strike 2"
            self.fps = 144
            self.config = self.LoadConfig()
            self.process = pw_module.open_process("cs2.exe")
            self.module = pw_module.get_module(self.process, "client.dll")["base"]
            self.trigger = TriggerBot(ignoreTeam=self.config["ignoreTeam"])
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
                backgroundColor=self.config["BackgroundBox"]
            )  # Initialize WallHack with TeamEsp option
        except:
            exit("Error: Enable only after opening Counter Strike 2")

    def LoadConfig(self):
        try:
            with open("config.json", "r", encoding="utf-8") as file:
                return load(file)
        except:
            exit("Error when importing configuration, see if the config.json file exists")

    async def Run(self):
        pw_module.overlay_init(target=self.window, title=self.window, fps=self.fps)
        
        # Create a listener for left Alt key press and release
        listener = pynput.keyboard.Listener(on_press=self.trigger.on_press, on_release=self.trigger.on_release)
        listener.start()

        while pw_module.overlay_loop():
            try:
                self.config = self.LoadConfig()  # Reload config each frame in case it's changed
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

                if self.config["BoxEsp"] or self.config["LineEsp"] or self.config["HeadEsp"] or self.config["DrawHealthBar"]:
                    self.wall.Render()

                if self.config["triggerbot"] and self.trigger.key_pressed:
                    await self.trigger.EnableAsync()

                # Drawing watermarks
                pw_module.draw_text("GHax", 10, 10, 14, pw_module.get_color("white"))  # Draw "GHax" at (10, 10) with font size 14 and white color
                pw_module.draw_text("Made by Cr0mb", 10, 30, 14, pw_module.get_color("white"))  # Draw "Made by Cr0mb" at (10, 30) with font size 14 and white color
                pw_module.draw_text("Discord: cr0mbleonthegame", 10, 50, 14, pw_module.get_color("white"))  # Draw "Discord: cr0mbleonthegame" at (10, 50) with font size 14 and white color
            except:
                pass

def main():
    root = tk.Tk()
    root.title("Config Editor")
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
            "triggerbot": True,
            "ignoreTeam": True,
            "TeamEsp": True
        }
    editor = ConfigEditor(root, config)
    root.mainloop()

if __name__ == "__main__":
    multiprocessing.Process(target=main).start()
    program = Program()
    asyncio.run(program.Run())
