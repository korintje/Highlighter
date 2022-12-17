# Author-korintje.
# Description-Highlighter

import adsk
import os, sys, configparser, traceback

# Global instances
core = adsk.core
fusion = adsk.fusion
app = core.Application.get()
if app:
    ui = app.userInterface
    product = app.activeProduct
    design = fusion.Design.cast(product)

# Global variables
handlers = []

# Global constants
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
RESOURCE_DIR = os.path.join(CURRENT_DIR, 'resources')
APPEARANCE_LIB_ID = 'BA5EE55E-9982-449B-9D66-9F036540E140'
DEFAULT_SCALE = 0.02
DEFAULT_OPACITY = 0.5
TLSTYLE = core.DropDownStyles.TextListDropDownStyle
NBFEATURE = fusion.FeatureOperations.NewBodyFeatureOperation
NCFEATURE = fusion.FeatureOperations.NewComponentFeatureOperation

# Appearance config
_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(RESOURCE_DIR, "colors"))
_options = _cfg["options"]
DEFAULT_COLOR_NAME = _options.get("default_value")
APPEARANCE_LIB_ID = _options.get("appearance_lib_id")
APPEARANCE_ID = _options.get("appearance_id")
HIGHLIGHT_COLORS = {}
try:
    for key, value in _cfg["rgbs"].items():
        HIGHLIGHT_COLORS[key] = [int(rgb.strip()) for rgb in value.strip().split(",")]
    HIGHLIGHT_COLORS["custom color"] = [128, 128, 128]
except:
    if ui:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Execute command handler
class CommandExecuteHandler(core.CommandEventHandler):

    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender
            inputs = command.commandInputs
            highlight = Highlight()
            isCustomColorUsed = False
            for ipt in inputs:
                if ipt.id == "selectedObjects":
                    obj_count = ipt.selectionCount
                    for i in range(obj_count):
                        selection = ipt.selection(i)
                        highlight.add_body(selection.entity)
                elif ipt.id == "offset":
                    highlight.set_offset(ipt.value)
                elif ipt.id == "opacity":
                    highlight.set_opacity(ipt.value)
                elif ipt.id == "colorName":
                    color_name = ipt.selectedItem.name
                    isCustomColorUsed = True if color_name == "custom color" else False
                    highlight.set_color_name(color_name)
                elif ipt.id == "red":
                    ipt.isEnabled = isCustomColorUsed
                    HIGHLIGHT_COLORS["custom color"][0] = ipt.value
                    ipt.value = HIGHLIGHT_COLORS[color_name][0]
                elif ipt.id == "green":
                    ipt.isEnabled = isCustomColorUsed
                    HIGHLIGHT_COLORS["custom color"][1] = ipt.value
                    ipt.value = HIGHLIGHT_COLORS[color_name][1]
                elif ipt.id == "blue":
                    ipt.isEnabled = isCustomColorUsed
                    HIGHLIGHT_COLORS["custom color"][2] = ipt.value
                    ipt.value = HIGHLIGHT_COLORS[color_name][2]
            highlight.build()
            args.isValidResult = True

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Destroy command handler
class CommandDestroyHandler(core.CommandEventHandler):

    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Command create handler
class CommandCreatedHandler(core.CommandCreatedEventHandler):

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False

            # Register to Execute command
            onExecute = CommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)

            # Register to ExecutePreview command
            onExecutePreview = CommandExecuteHandler()
            cmd.executePreview.add(onExecutePreview)
            handlers.append(onExecutePreview)

            # Register to Destroy command
            onDestroy = CommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            handlers.append(onDestroy)
            
            # Add inputs of molecular settings
            inputs: adsk.core.CommandInputs = cmd.commandInputs
            selIpt = inputs.addSelectionInput('selectedObjects', 'Select objects', 'select target object')
            selIpt.setSelectionLimits(0)
            selIpt.addSelectionFilter("SolidBodies")

            # Add inputs of offset
            inputs.addFloatSpinnerCommandInput("offset", "Offset", "cm", 0.0, 100.0, 0.01, DEFAULT_SCALE)

            # Add inputs of opacity
            inputs.addFloatSpinnerCommandInput("opacity", "Opacity", "", 0.0, 1.0, 0.1, DEFAULT_OPACITY)

            # Add inputs of highlight color name
            color_input = inputs.addDropDownCommandInput("colorName", "Color name", TLSTYLE)
            for color_name in HIGHLIGHT_COLORS.keys():
                is_selected = True if color_name == DEFAULT_COLOR_NAME else False
                color_input.listItems.add(color_name, is_selected)

            # Add inputs of custom RGB if Custom color is selected
            inputs.addIntegerSpinnerCommandInput("red", "R", 0, 255, 1, 128)
            inputs.addIntegerSpinnerCommandInput("green", "G", 0, 255, 1, 128)
            inputs.addIntegerSpinnerCommandInput("blue", "B", 0, 255, 1, 128)

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Molecular model class
class Highlight:

    def __init__(self):
        self.selected_bodies = []
        self.offset = adsk.core.ValueInput.createByReal(DEFAULT_SCALE)
        self.color_name = DEFAULT_COLOR_NAME
        self.opacity = DEFAULT_OPACITY
    
    def add_body(self, body):
        self.selected_bodies.append(body)
    
    def set_offset(self, value):
        self.offset = adsk.core.ValueInput.createByReal(value)
    
    def set_color_name(self, color_name):
        self.color_name = color_name
    
    def set_opacity(self, value):
        self.opacity = value

    def build(self):
        try:
            # Get material and appearance libraries
            materialLibs = app.materialLibraries
            presetAppearances = materialLibs.itemById(APPEARANCE_LIB_ID).appearances
            favoriteAppearances = design.appearances

            # Get current component
            comp = design.activeComponent 

            # Create offset features
            offsetFeats = comp.features.offsetFeatures

            # Create input entities for offset feature
            inputFaces = adsk.core.ObjectCollection.create()
            for body in self.selected_bodies:
                for face in body.faces:
                    inputFaces.add(face)

            # Early return if no body selected
            if inputFaces.count < 1:
                return True
            
            # Create the offset feature
            offsetInput = offsetFeats.createInput(inputFaces, self.offset, NCFEATURE)
            offsetFeat = offsetFeats.add(offsetInput)

            # Set appearance
            highlight_color_name = f'highlight_{self.color_name}'
            # color = [int(rgb.strip()) for rgb in HIGHLIGHT_COLORS[self.color_name].strip().split(",")]
            color = HIGHLIGHT_COLORS[self.color_name]
            try:
                highlightColor = favoriteAppearances.itemByName(highlight_color_name)
            except:
                highlightColor = None
            if not highlightColor:
                baseColor = presetAppearances.itemById(APPEARANCE_ID)
                newColor = favoriteAppearances.addByCopy(baseColor, highlight_color_name)
                colorProp = core.ColorProperty.cast(newColor.appearanceProperties.itemById('opaque_albedo'))
                colorProp.value = core.Color.create(*color, 0)
                highlightColor = favoriteAppearances.itemByName(highlight_color_name)
            for body in offsetFeat.parentComponent.bRepBodies:
                body.appearance = highlightColor
                body.opacity = self.opacity

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))     


# Entry point of the script
def run(context):

    try:

        # Check design exiss
        if not design:
            ui.messageBox('It is not supported in current workspace.')
            return

        # Check the command exists or not
        commandDefinitions = ui.commandDefinitions
        cmdDef = commandDefinitions.itemById('Highlight')
        if not cmdDef:
            cmdDef = commandDefinitions.addButtonDefinition(
                'Highlight',
                'Highlight selected objects',
                'Highlight selected objects.',
                './resources'
            )

        # Register to commandCreated event
        onCommandCreated = CommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        handlers.append(onCommandCreated)
        inputs = core.NamedValues.create()
        cmdDef.execute(inputs)
        adsk.autoTerminate(False)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
