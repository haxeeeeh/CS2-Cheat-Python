import sys
import os
import time
import keyboard
import winsound
import PyQt5
import pymem

from pynput.mouse import Controller, Button
import pyMeow as pw_module
import pymem.process

from random import uniform
from requests import get
from win32gui import GetWindowText, GetForegroundWindow

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QLabel,
    QColorDialog,
    QFontDialog,
    QInputDialog,
    QMessageBox,
    QDialog,
)




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

class TriggerBot:
    def __init__(self, triggerKey="shift", shootTeammates=False):
        self.triggerKey = triggerKey
        self.shootTeammates = shootTeammates  # Added shootTeammates attribute
        self.pm = pymem.Pymem("cs2.exe")
        self.client = pymem.process.module_from_name(self.pm.process_handle, "client.dll").lpBaseOfDll
        self.offsets_manager = Offsets()
        self.mouse = Controller()  # Create an instance of the Controller class

    def shoot(self):
        time.sleep(uniform(0.01 , 0.05))
        self.mouse.click(Button.left)  # Use the mouse object to click the left button

    def enable(self):
        try:
            if not GetWindowText(GetForegroundWindow()) == "Counter-Strike 2":
                return

            if keyboard.is_pressed(self.triggerKey):
                player = self.pm.read_longlong(self.client + self.offsets_manager.dwLocalPlayerPawn)
                entityId = self.pm.read_int(player + self.offsets_manager.m_iIDEntIndex)

                if entityId > 0:
                    entList = self.pm.read_longlong(self.client + self.offsets_manager.dwEntityList)

                    entEntry = self.pm.read_longlong(entList + 0x8 * (entityId >> 9) + 0x10)
                    entity = self.pm.read_longlong(entEntry + 120 * (entityId & 0x1FF))

                    entityTeam = self.pm.read_int(entity + self.offsets_manager.m_iTeamNum)
                    entityHp = self.pm.read_int(entity + self.offsets_manager.m_iHealth)

                    playerTeam = self.pm.read_int(player + self.offsets_manager.m_iTeamNum)

                    if entityTeam != 0 and entityHp > 0:
                        if self.shootTeammates or (entityTeam != playerTeam):
                            self.shoot()
        except KeyboardInterrupt:
            pass
        except:
            pass  # Do nothing, simply ignore any exceptions



    def toggle_shoot_teammates(self, state):
        self.shootTeammates = state == Qt.Checked




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

    def Name(self):
        player_name = pw_module.r_string(self.process, self.pointer + Offsets.m_iszPlayerName, 32)
        return player_name.split("\x00")[0]

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

    # Define bone positions for hands, legs, chest, and head
    BONE_POSITIONS = {
        "head": 6,  # Head bone index
        "chest": 15,  # Chest bone index
        "left_hand": 10,  # Left hand bone index
        "right_hand": 2,  # Right hand bone index
        "left_leg": 23,  # Left leg bone index
        "right_leg": 26,  # Right leg bone index
    }
    
    
    
    def __init__(self, process, module):
        self.process = process
        self.module = module
        self.enabled = True  # Initially enable wallhack
        self.watermark_enabled = True  # Watermark initially enabled
        self.box_esp_enabled = False
        self.healthbar_enabled = False
        self.health_esp_enabled = False
        self.enemy_only_enabled = False
        self.team_only_enabled = False
        self.team_esp_color = "blue"  # Default color is blue for team
        self.box_esp_color = "red"  # Default color is red for enemy
        self.esp_font_settings = {"size": 10, "color": "cyan"}  # Default font settings for ESP
        self.name_esp_enabled = False
        self.line_esp_enabled = False
        self.head_esp_enabled = False
        self.head_esp_shape = "square"  # Default head ESP shape is square
        self.head_esp_size = 10  # Default head ESP size
        self.head_esp_color = "yellow"  # Default head ESP color
        self.line_color = "green"  # Default color for line ESP
        self.skeletonesp = False  # Skeleton ESP initially disabled
        self.skeleton_esp_color = "orange"  # Default color for skeleton ESP
        self.bone_esp_enabled = False
        self.bone_esp_shape = "square"  # Default bone ESP shape is square
        self.bone_esp_size = 5  # Default bone ESP size
        self.bone_esp_color = "yellow"  # Default bone ESP color
        self.box_background_color = "black"  # Default color for box background
        self.crosshair_enabled = False
        self.crosshair_color = "white"




        # Define bone connections for drawing skeleton
        self.BONE_CONNECTIONS = [
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

    def Toggle(self, state):
        self.enabled = state
        
    def ToggleWatermark(self, state):
        self.watermark_enabled = state

    def ToggleBoxESP(self, state):
        self.box_esp_enabled = state

    def ToggleHealthBar(self, state):
        self.healthbar_enabled = state

    def ToggleHealthESP(self, state):
        self.health_esp_enabled = state

    def ToggleEnemyOnly(self, state):
        self.enemy_only_enabled = state

    def ToggleTeamOnly(self, state):
        self.team_only_enabled = state

    def ToggleNameESP(self, state):
        self.name_esp_enabled = state

    def ToggleLineESP(self, state):
        self.line_esp_enabled = state

    def ToggleHeadESP(self, state):
        self.head_esp_enabled = state

    def ToggleSkeletonESP(self, state):
        self.skeletonesp = state

    def ChangeBoxESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.box_esp_color = color.name()

    def ChangeTeamESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.team_esp_color = color.name()

    def ChangeESPFontSize(self):
        size, ok = QInputDialog.getInt(None, "Font Size", "Enter Font Size:", value=self.esp_font_settings["size"])
        if ok:
            self.esp_font_settings["size"] = size


    def ChangeESPFontColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.esp_font_settings["color"] = color.name()

    def ChangeLineESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.line_color = color.name()

    def ChangeHeadESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.head_esp_color = color.name()

    def ChangeHeadESPSize(self):
        size, ok = QInputDialog.getInt(None, "Head ESP Size", "Enter Head ESP Size:", value=self.head_esp_size)
        if ok:
            self.head_esp_size = size

    def ChangeHeadESPShape(self):
        items = ("square", "circle")
        item, ok = QInputDialog.getItem(None, "Head ESP Shape", "Select Head ESP Shape:", items, 0, False)
        if ok and item:
            self.head_esp_shape = item.lower()

    def ChangeSkeletonESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.skeleton_esp_color = color.name()

    def ToggleBoneESP(self, state):
        self.bone_esp_enabled = state

    def ChangeBoneESPSize(self):
        size, ok = QInputDialog.getInt(None, "Bone ESP Size", "Enter Bone ESP Size:", value=self.bone_esp_size)
        if ok:
            self.bone_esp_size = size

    def ChangeBoneESPShape(self):
        items = ("square", "circle")
        item, ok = QInputDialog.getItem(None, "Bone ESP Shape", "Select Bone ESP Shape:", items, 0, False)
        if ok and item:
            self.bone_esp_shape = item.lower()

    def ChangeBoneESPColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.bone_esp_color = color.name()

    def RenderBoneESP(self, entity, matrix):
        if not self.bone_esp_enabled:
            return

        for bone_name, bone_index in self.BONE_POSITIONS.items():
            bone_pos = entity.BonePos(bone_index)
            try:
                bone_screen_pos = pw_module.world_to_screen(matrix, bone_pos, 1)
            except:
                continue

            if bone_screen_pos:
                if self.bone_esp_shape == "square":
                    pw_module.draw_rectangle_lines(bone_screen_pos["x"] - self.bone_esp_size / 2, bone_screen_pos["y"] - self.bone_esp_size / 2, 
                                                    self.bone_esp_size, self.bone_esp_size, pw_module.get_color(self.bone_esp_color), 1)
                elif self.bone_esp_shape == "circle":
                    pw_module.draw_circle_lines(bone_screen_pos["x"], bone_screen_pos["y"], self.bone_esp_size / 2, pw_module.get_color(self.bone_esp_color))

    def ChangeBoxBackgroundColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.box_background_color = color.name()

    def ToggleCrosshair(self, state):
        self.crosshair_enabled = state

    def ChangeCrosshairColor(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color.isValid():
            self.crosshair_color = color.name()

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

            yield Entity(controllerPointer, pawnPointer, self.process)

    def Render(self):
        if not self.enabled:
            return

        matrix = pw_module.r_floats(self.process, self.module + Offsets.dwViewMatrix, 16)

        for entity in self.GetEntities():
            if entity.Wts(matrix) and entity.Health() > 0:
                if self.enemy_only_enabled and not self.team_only_enabled and entity.Team() != 2:  # Modified: Check if "Enemy Only" is enabled and entity is an enemy
                    continue  # Skip rendering if "Enemy Only" is enabled and the entity is not an enemy
                elif self.team_only_enabled and not self.enemy_only_enabled and entity.Team() == 2:  # New: Check if "Team Only" is enabled and entity is a teammate
                    continue  # Skip rendering if "Team Only" is enabled and the entity is not a teammate

                head = entity.pos2d["y"] - entity.headPos2d["y"]
                width = head / 2
                center = width / 2

                if entity.Team() == 2:  # Enemy
                    color = pw_module.get_color(self.box_esp_color)
                else:  # Teammate
                    color = pw_module.get_color(self.team_esp_color)

                if self.box_esp_enabled:
                    # Box background
                    fill = pw_module.fade_color(pw_module.get_color(self.box_background_color), 0.5)
                    pw_module.draw_rectangle(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, fill)

                    # Box
                    pw_module.draw_rectangle_lines(entity.headPos2d["x"] - center, entity.headPos2d["y"] - center / 2, width, head + center / 2, color, 0.8)
                    
                if self.healthbar_enabled:
                    # Health Bar
                    bar_height = head * (entity.Health() / 90)
                    bar_width = 3
                    bar_x = entity.headPos2d["x"] - center - 2 - bar_width
                    bar_y = entity.headPos2d["y"] + head / 1
                    bar_color = pw_module.get_color("green") if entity.Health() > 50 else pw_module.get_color("red")

                    # Black outline behind health bar
                    pw_module.draw_rectangle(bar_x - 1, bar_y - bar_height - 1, bar_width + 2, bar_height + 2, pw_module.get_color("black"))

                    # Health bar
                    pw_module.draw_rectangle(bar_x, bar_y - bar_height, bar_width, bar_height, bar_color)

                if self.health_esp_enabled:
                    # Health Text
                    hp_text = f"HP: {entity.Health()}%"
                    hp_text_size = self.esp_font_settings["size"]
                    hp_text_color = pw_module.get_color(self.esp_font_settings["color"])
                    hp_text_x = entity.headPos2d["x"] + center + 2
                    hp_text_y = entity.headPos2d["y"] - center + 10
                    pw_module.draw_text(hp_text, hp_text_x, hp_text_y, hp_text_size, hp_text_color)

                if self.name_esp_enabled:
                    # Name ESP
                    player_name = entity.Name()
                    name_size = self.esp_font_settings["size"]
                    name_color = pw_module.get_color(self.esp_font_settings["color"])
                    name_x = entity.headPos2d["x"] - (pw_module.measure_text(player_name, name_size) / 2)  # Centering the name
                    name_y = entity.headPos2d["y"] - center - 10  # Adjust position as needed
                    pw_module.draw_text(player_name, name_x, name_y, name_size, name_color)

                if self.line_esp_enabled:
                    # Line ESP
                    screen_center_x, screen_height = pw_module.get_screen_width() / 2, pw_module.get_screen_height()
                    line_color = self.line_color
                    pw_module.draw_line(screen_center_x, screen_height, entity.headPos2d["x"], entity.headPos2d["y"], pw_module.get_color(line_color))

                if self.head_esp_enabled:
                    # Head ESP
                    head_size = self.head_esp_size
                    head_color = pw_module.get_color(self.head_esp_color)

                    if self.head_esp_shape == "square":
                        pw_module.draw_rectangle_lines(entity.headPos2d["x"] - head_size / 2, entity.headPos2d["y"] - head_size / 2, head_size, head_size, head_color, 1)
                    elif self.head_esp_shape == "circle":
                        pw_module.draw_circle_lines(entity.headPos2d["x"], entity.headPos2d["y"], head_size / 2, head_color)

                if self.bone_esp_enabled:
                    self.RenderBoneESP(entity, matrix)

                if self.crosshair_enabled:
                    screen_center_x, screen_center_y = pw_module.get_screen_width() / 2, pw_module.get_screen_height() / 2
                    crosshair_size = 10
                    crosshair_color = pw_module.get_color(self.crosshair_color)
                    pw_module.draw_line(screen_center_x - crosshair_size, screen_center_y, screen_center_x + crosshair_size, screen_center_y, crosshair_color)
                    pw_module.draw_line(screen_center_x, screen_center_y - crosshair_size, screen_center_x, screen_center_y + crosshair_size, crosshair_color)

                if self.watermark_enabled:
                    # Watermark rendering
                    watermark_text_color = pw_module.get_color("white")
                    watermark_background_color = pw_module.get_color("black")
                    watermark_text_size = 20
                    watermark_text_1 = "GHax"
                    watermark_text_2 = "Made By Cr0mb"
                            
                    # Get text dimensions
                    text_width_1 = pw_module.measure_text(watermark_text_1, watermark_text_size)
                    text_width_2 = pw_module.measure_text(watermark_text_2, watermark_text_size)
                            
                    # Calculate background dimensions
                    background_width = max(text_width_1, text_width_2) + 20
                    background_height = 60
                            
                    # Draw background rectangle
                    pw_module.draw_rectangle(10, 10, background_width, background_height, watermark_background_color)
                            
                    pw_module.draw_text(watermark_text_1, 20, 20, watermark_text_size, watermark_text_color)
                    pw_module.draw_text(watermark_text_2, 20, 40, 15, watermark_text_color)

                if self.skeletonesp:
                    # Skeleton ESP
                    skeleton_color = pw_module.get_color(self.skeleton_esp_color)
                    for bone_start, bone_end in self.BONE_CONNECTIONS:
                        start_pos = entity.BonePos(bone_start)
                        end_pos = entity.BonePos(bone_end)

                        try:
                            start_pos_screen = pw_module.world_to_screen(matrix, start_pos, 1)
                            end_pos_screen = pw_module.world_to_screen(matrix, end_pos, 1)
                        except Exception as e:
                            continue

                        if start_pos_screen and end_pos_screen:
                            start_x, start_y = start_pos_screen["x"], start_pos_screen["y"]
                            end_x, end_y = end_pos_screen["x"], end_pos_screen["y"]

                            pw_module.draw_line(start_x, start_y, end_x, end_y, skeleton_color)

        pw_module.end_drawing()


class SetTriggerKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Trigger Key")
        self.setModal(True)

        layout = QVBoxLayout()
        label = QLabel("Press the key you want to use as the trigger key...")
        layout.addWidget(label)

        self.setLayout(layout)

    def keyPressEvent(self, event):
        self.accept()
        winsound.Beep(1000, 200)


class Program:
    def __init__(self):
        try:
            self.fps = 144
            self.process = pw_module.open_process("cs2.exe")
            self.module = pw_module.get_module(self.process, "client.dll")["base"]
            self.wall = WallHack(self.process, self.module)
            self.triggerbot = None
            self.trigger_key = None 
            self.trigger_team = False 
            self.create_gui()
        except:
            exit("Error: Enable only after opening Counter Strike 2")

    def create_gui(self):
        self.window = QWidget()
        self.window.setWindowTitle("GHax V1.7")
        self.window.setStyleSheet("background-color: #23272A;")
        self.window.setGeometry(100, 100, 400, 400)

        layout = QHBoxLayout() 

        checkboxes_layout = QVBoxLayout()  
        checkboxes = [
            ("Watermark", self.toggle_watermark), 
            ("T Side Only", self.toggle_enemy_only),
            ("CT Side Only", self.toggle_team_only),
            ("Box ESP", self.toggle_box_esp),
            ("Health Bar", self.toggle_healthbar),
            ("Health ESP", self.toggle_health_esp),
            ("Name ESP", self.toggle_name_esp),
            ("Line ESP", self.toggle_line_esp),
            ("Head ESP", self.toggle_head_esp),
            ("Skeleton ESP", self.toggle_skeleton_esp),
            ("Bone ESP", self.toggle_bone_esp),
            ("Triggerbot", self.toggle_triggerbot), 
        ]

        for text, function in checkboxes:
            checkbox = QCheckBox(text)
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: white;
                }
                QCheckBox::indicator {
                    border: 2px solid white;
                    width: 20px;
                    height: 20px;
                }
                QCheckBox::indicator:checked {
                    background-color: purple;
                    border: 2px solid purple;
                }
                QCheckBox::indicator:hover {
                    border: 2px solid purple;
                }
            """)
            checkbox.stateChanged.connect(function)
            checkboxes_layout.addWidget(checkbox)
            if text == "Watermark":  
                checkbox.setChecked(self.wall.watermark_enabled)

        shoot_teammates_checkbox = QCheckBox("Shoot Teammates")
        shoot_teammates_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
            }
            QCheckBox::indicator {
                border: 2px solid white;
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:checked {
                background-color: purple;
                border: 2px solid purple;
            }
            QCheckBox::indicator:hover {
                border: 2px solid purple;
            }
        """)
        shoot_teammates_checkbox.stateChanged.connect(self.toggle_shoot_teammates)
        checkboxes_layout.addWidget(shoot_teammates_checkbox)

        buttons_layout = QVBoxLayout() 
        buttons = [
            ("Box Background Color", self.wall.ChangeBoxBackgroundColor),
            ("Skeleton ESP Color", self.wall.ChangeSkeletonESPColor),
            ("Change Bone ESP Size", self.wall.ChangeBoneESPSize),
            ("Change Bone ESP Shape", self.wall.ChangeBoneESPShape),
            ("Change Bone ESP Color", self.wall.ChangeBoneESPColor),
            ("Change Font Color", self.wall.ChangeESPFontColor),
            ("Change Font Size", self.wall.ChangeESPFontSize),
            ("Box Enemy Color", self.wall.ChangeBoxESPColor),
            ("Box Team Color", self.wall.ChangeTeamESPColor),
            ("Line Color", self.wall.ChangeLineESPColor),
            ("Head ESP Color", self.wall.ChangeHeadESPColor),
            ("Head ESP Size", self.wall.ChangeHeadESPSize),
            ("Head ESP Shape", self.wall.ChangeHeadESPShape),
            ("Set Trigger Key", self.set_trigger_key), 
        ]

        for text, function in buttons:
            button = QPushButton(text)
            button.setStyleSheet("""
                QPushButton {
                    color: white;
                    border: 2px solid white;
                    padding: 5px 10px;
                    margin: 0px;
                }
                QPushButton:hover {
                    background-color: purple;
                    border: 2px solid purple;
                }
            """)
            button.clicked.connect(function)
            buttons_layout.addWidget(button)

        # Checkbox to toggle crosshair
        crosshair_checkbox = QCheckBox("Crosshair")
        crosshair_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
            }
            QCheckBox::indicator {
                border: 2px solid white;
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:checked {
                background-color: purple;
                border: 2px solid purple;
            }
            QCheckBox::indicator:hover {
                border: 2px solid purple;
            }
        """)
        crosshair_checkbox.stateChanged.connect(self.toggle_crosshair)
        checkboxes_layout.addWidget(crosshair_checkbox)

        # Button to change crosshair color
        crosshair_color_button = QPushButton("Change Crosshair Color")
        crosshair_color_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #7289DA;
                border: 2px solid white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #677BC4;
            }
        """)
        crosshair_color_button.clicked.connect(self.change_crosshair_color)
        checkboxes_layout.addWidget(crosshair_color_button)

        layout.addLayout(checkboxes_layout) 
        layout.addLayout(buttons_layout) 
        
        self.window.setLayout(layout)
        self.window.show()

    def toggle_shoot_teammates(self, state):
        self.trigger_team = state == Qt.Checked

    def toggle_box_esp(self, state):
        self.wall.ToggleBoxESP(state == Qt.Checked)

    def toggle_healthbar(self, state):
        self.wall.ToggleHealthBar(state == Qt.Checked)

    def toggle_health_esp(self, state):
        self.wall.ToggleHealthESP(state == Qt.Checked)

    def toggle_enemy_only(self, state):
        self.wall.ToggleEnemyOnly(state == Qt.Checked)

    def toggle_team_only(self, state):
        self.wall.ToggleTeamOnly(state == Qt.Checked)

    def toggle_name_esp(self, state):
        self.wall.ToggleNameESP(state == Qt.Checked)

    def toggle_line_esp(self, state):
        self.wall.ToggleLineESP(state == Qt.Checked)

    def toggle_head_esp(self, state):
        self.wall.ToggleHeadESP(state == Qt.Checked)

    def toggle_bone_esp(self):
        state = self.wall.bone_esp_enabled
        self.wall.ToggleBoneESP(not state)

    def toggle_skeleton_esp(self, state):
        self.wall.ToggleSkeletonESP(state == Qt.Checked)

    def toggle_watermark(self, state):
        self.wall.ToggleWatermark(state == Qt.Checked)


    def toggle_crosshair(self, state):
        self.wall.ToggleCrosshair(state == Qt.Checked)

    def change_crosshair_color(self):
        self.wall.ChangeCrosshairColor()

    def toggle_triggerbot(self, state):
        if state == Qt.Checked:
            if not self.trigger_key:  
                self.set_trigger_key()
                if not self.trigger_key: 
                   
                    return
            self.triggerbot = TriggerBot(triggerKey=self.trigger_key, shootTeammates=self.trigger_team)
        else:
            self.triggerbot = None

    def toggle_shoot_teammates(self, state):
        self.trigger_team = state == Qt.Checked
        if self.triggerbot:
            self.triggerbot.shootTeammates = self.trigger_team
            
    def set_trigger_key(self):
        dialog = SetTriggerKeyDialog(self.window)
        if dialog.exec_():
            pressed_key = keyboard.read_event(suppress=True)
            self.trigger_key = pressed_key.name
            print(f"Trigger key set to: {self.trigger_key}")

            if self.triggerbot:
                self.triggerbot.triggerKey = self.trigger_key


    def Run(self):
        pw_module.overlay_init(target=self.window.windowTitle(), title=self.window.windowTitle(), fps=self.fps)

        while pw_module.overlay_loop():
            try:
                if self.wall.enabled:
                    self.wall.Render()
                if self.triggerbot:  
                    self.triggerbot.enable()
            except:
                pass
            QApplication.processEvents()


if __name__ == "__main__":
    app = QApplication([])
    program = Program()
    program.Run()
    app.exec_()
