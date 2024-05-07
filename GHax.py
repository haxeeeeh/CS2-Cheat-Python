# + update added +

# > squarebone esp
# > updated crosshair
# > updated teamesp to enemyonly
# > no longer renders wallhack on local player.
# > fixed major error Error: 299 - Only part of a ReadProcessMemory or WriteProcessMemory request has been performed
# > added name & health text color
# > added updates to json reading to remove bugs when making updates to config.json
# > removed tkinter gui window (for now)

import pyMeow as pw_module
from json import load
from requests import get
import keyboard
from time import sleep
from pynput.mouse import Button, Controller
from win32gui import GetWindowText, GetForegroundWindow

class Offsets:
    try:
        offset = get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json").json()
        client = get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client.dll.json").json()

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

    def Name(self):
        return pw_module.r_string(self.process, self.pointer + Offsets.m_iszPlayerName)

    def draw_circle_bones(self, matrix, color):
        screen_width, screen_height = pw_module.get_screen_width(), pw_module.get_screen_height()
        
        # Define the bone indices for the bones to draw circles over
        bone_indices = [6, 15, 10, 2, 23, 26]  # Indices for head, hand_R, hand_L, leg_upper_L, leg_upper_R
        
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

    def draw_square_bones(self, matrix, color):
        screen_width, screen_height = pw_module.get_screen_width(), pw_module.get_screen_height()
        
        # Define the bone indices for the bones to draw squares around
        bone_indices = [6, 15, 10, 2, 23, 26]  # Indices for head, hand_R, hand_L, leg_upper_L, leg_upper_R
        
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
                    pw_module.draw_rectangle_lines(bone_x - 5, bone_y - 5, 10, 10, pw_module.get_color(color), 1)


    def draw_skeleton(self, matrix, color):
        screen_width, screen_height = pw_module.get_screen_width(), pw_module.get_screen_height()
        
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
        (9, 10), 
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


class WallHack:
    def __init__(self, process, module, config):
        self.process = process
        self.module = module
        self.config = config

    def GetEntities(self):
        entityList = pw_module.r_int64(self.process, self.module + Offsets.dwEntityList)
        localPlayer = pw_module.r_int64(self.process, self.module + Offsets.dwLocalPlayerController)

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

            entity = Entity(controllerPointer, pawnPointer, self.process)
            if self.config.get("enemyOnly", False) and entity.Team() != 2:  
                continue
            yield entity

    def Render(self):
        matrix = pw_module.r_floats(self.process, self.module + Offsets.dwViewMatrix, 16)
        boxbackground = self.config.get("boxbackground", "black")  # Fetching box background color from config
        
        for entity in self.GetEntities():
            if entity.Wts(matrix) and entity.Health() > 0:
                head = entity.pos2d["y"] - entity.headPos2d["y"]
                width = head / 2
                center = width / 2
                color = pw_module.get_color(self.config.get("enemycolor", "red")) if entity.Team() == 2 else pw_module.get_color(self.config.get("teamcolor", "blue"))
                fill = pw_module.fade_color(pw_module.get_color(boxbackground), 0.5)  # Applying box background color with opacity

                # Fill
                pw_module.draw_rectangle(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, fill)

                # Box
                pw_module.draw_rectangle_lines(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, color, 0.8)

                # Head ESP
                if self.config.get("headesp", False):
                    head_size = 10  
                    head_color = pw_module.get_color(self.config.get("headcolor", "purple"))
                    head_shape = self.config.get("headshape", "square")

                    if head_shape == "square":
                        pw_module.draw_rectangle_lines(entity.headPos2d["x"] - head_size / 2, entity.headPos2d["y"] - head_size / 2, head_size, head_size, head_color, 1)
                    elif head_shape == "circle":
                        pw_module.draw_circle_lines(entity.headPos2d["x"], entity.headPos2d["y"], head_size / 2, head_color)


                # Line ESP
                if self.config.get("lineEsp", False):
                    screen_center_x, screen_height = pw_module.get_screen_width() / 2, pw_module.get_screen_height()
                    line_color = self.config.get("lineColor", "white")
                    pw_module.draw_line(screen_center_x, screen_height, entity.headPos2d["x"], entity.headPos2d["y"], pw_module.get_color(line_color))

                # Name ESP
                if self.config.get("nameesp", False):
                    player_name = entity.Name()
                    name_size = self.config.get("namesize", 10)
                    name_color = pw_module.get_color(self.config.get("namecolor", "white"))
                    name_x = entity.headPos2d["x"] - (pw_module.measure_text(player_name, name_size) / 2)  # Centering the name
                    name_y = entity.headPos2d["y"] - center - 10  # Adjust position as needed
                    pw_module.draw_text(player_name, name_x, name_y, name_size, name_color)

                # Circle Bone ESP
                if self.config.get("circleboneesp", False):
                    circle_bone_color = self.config.get("circlebonecolor", "purple")
                    entity.draw_circle_bones(matrix, circle_bone_color)

                # Square Bone ESP
                if self.config.get("squareboneesp", False):
                    square_bone_color = self.config.get("squarebonecolor", "blue")
                    entity.draw_square_bones(matrix, square_bone_color)


                # Watermark
                if self.config.get("watermark", False):
                    watermark_text_color = pw_module.get_color("white")
                    watermark_background_color = pw_module.get_color("black")  # New line
                    watermark_text_size = 20
                    watermark_text_1 = "GHax"
                    watermark_text_2 = "Made By Cr0mb"
                    
                    # Get text dimensions
                    text_width_1 = pw_module.measure_text(watermark_text_1, watermark_text_size)
                    text_width_2 = pw_module.measure_text(watermark_text_2, watermark_text_size)
                    
                    # Calculate background dimensions
                    background_width = max(text_width_1, text_width_2) + 20  # Add padding
                    background_height = 60  # Total height for both lines
                    
                    # Draw background rectangle
                    pw_module.draw_rectangle(10, 10, background_width, background_height, watermark_background_color)
                    
                    # Draw text on top of the background
                    pw_module.draw_text(watermark_text_1, 20, 20, watermark_text_size, watermark_text_color)
                    pw_module.draw_text(watermark_text_2, 20, 40, 15, watermark_text_color)


                
                # Crosshair
                if self.config.get("crosshair", False):
                    screen_center_x, screen_center_y = pw_module.get_screen_width() / 2, pw_module.get_screen_height() / 2
                    crosshair_size = 10
                    crosshair_color = pw_module.get_color("white")
                    pw_module.draw_line(screen_center_x - crosshair_size, screen_center_y, screen_center_x + crosshair_size, screen_center_y, crosshair_color)
                    pw_module.draw_line(screen_center_x, screen_center_y - crosshair_size, screen_center_x, screen_center_y + crosshair_size, crosshair_color)

                # Health Bar
                if self.config.get("healthbar", False):
                    bar_height = head * (entity.Health() / 90)  
                    bar_width = 3  
                    bar_x = entity.headPos2d["x"] - center - 2 - bar_width  
                    bar_y = entity.headPos2d["y"] + head / 1  
                    bar_color = pw_module.get_color("green") if entity.Health() > 50 else pw_module.get_color("red")

                    # Black outline behind health bar
                    pw_module.draw_rectangle(bar_x - 1, bar_y - bar_height - 1, bar_width + 2, bar_height + 2, pw_module.get_color("black"))

                    # Health bar
                    pw_module.draw_rectangle(bar_x, bar_y - bar_height, bar_width, bar_height, bar_color)

                # Health Text
                if self.config.get("healthesp", False):
                    hp_text = f"HP: {entity.Health()}"
                    hp_text_size = self.config.get("healthsize", 10)
                    hp_text_color = pw_module.get_color(self.config.get("healthcolor", "white"))
                    hp_text_x = entity.headPos2d["x"] + center + 2  
                    hp_text_y = entity.headPos2d["y"] - center + 10  
                    pw_module.draw_text(hp_text, hp_text_x, hp_text_y, hp_text_size, hp_text_color)

                # Skeleton ESP
                if self.config.get("skeletonesp", False):
                    skeleton_color = self.config.get("skeletoncolor", "orange")
                    entity.draw_skeleton(matrix, skeleton_color)

        pw_module.end_drawing()


class Program:
    def __init__(self):
        try:
            self.window = "Counter-Strike 2"
            self.fps = 144
            self.process = pw_module.open_process("cs2.exe")
            self.module = pw_module.get_module(self.process, "client.dll")["base"]
            self.config = self.LoadConfig()
            self.wall = WallHack(self.process, self.module, self.config)
            self.triggerbot_enabled = self.config.get("Triggerbot", False)
            self.trigger_key = self.config.get("triggerKey", "shift")
            self.triggerbot_on_same_team = self.config.get("triggerbotOnSameTeam", False)
        except:
            exit("Error: Enable only after opening Counter Strike 2")

    def LoadConfig(self):
        try:
            with open("config.json", "r", encoding="utf-8") as file:
                return load(file)
        except:
            exit("Error when importing configuration, see if the config.json file exists")

    def Run(self):
        pw_module.overlay_init(target=self.window, title=self.window, fps=self.fps)

        while pw_module.overlay_loop():
            try:
                # Check for config updates
                new_config = self.LoadConfig()
                if new_config != self.config:
                    self.config = new_config
                    self.wall = WallHack(self.process, self.module, self.config)
                    self.triggerbot_enabled = self.config.get("Triggerbot", False)
                    self.trigger_key = self.config.get("triggerKey", "shift")
                    self.triggerbot_on_same_team = self.config.get("triggerbotOnSameTeam", False)

                if self.config.get("boxesp", False):
                    self.wall.Render()

                # Triggerbot functionality
                if self.triggerbot_enabled and GetWindowText(GetForegroundWindow()) == "Counter-Strike 2" and keyboard.is_pressed(self.trigger_key):
                    self.triggerbot()
            except:
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
                sleep(delay)
                mouse = Controller()
                mouse.click(Button.left)


if __name__ == "__main__":
    program = Program()
    program.Run()
