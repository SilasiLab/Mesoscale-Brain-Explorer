#!/usr/bin/env python3

import ast
import functools
import os
import pickle
import uuid

import qtutil
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from . import constants
from . import file_io
from .custom_qt_items import CheckableComboBox, PlayerDialog
from .file_io import load_reference_frame


def save_project(video_path, project, frames, manip, file_type):
    name_before, ext = os.path.splitext(os.path.basename(video_path))
    file_before = [files for files in project.files if files['name'] == name_before]
    assert(len(file_before) == 1)
    file_before = file_before[0]
    # check if one with same name already exists and don't overwrite if it does
    name_after = file_io.get_name_after_no_overwrite(name_before, manip, project)

    path = str(os.path.normpath(os.path.join(project.path, name_after) + '.npy'))
    if frames is not None:
        if os.path.isfile(path):
            progress = QProgressDialog('Deleting ' + path, 'Abort', 0, 100)
            progress.setAutoClose(True)
            progress.setMinimumDuration(0)
            def callback_del(x):
                progress.setValue(x * 100)
                QApplication.processEvents()
            callback_del(0)
            os.remove(path)
            callback_del(1)
        progress = QProgressDialog('Saving ' + path + ' to file. This could take a few minutes.', 'Abort', 0, 100)
        progress.setAutoClose(True)
        progress.setMinimumDuration(0)
        def callback_save(x):
            progress.setValue(x * 100)
            QApplication.processEvents()
        callback_save(0)
        file_io.save_file(path, frames)
        callback_save(1)
    if not file_before['manipulations'] == []:
        project.files.append({
            'path': os.path.normpath(path),
            'type': file_type,
            'source_video': video_path,
            'manipulations': str(ast.literal_eval(file_before['manipulations']) + [manip]),
            'name': name_after
        })
    else:
        project.files.append({
            'path': os.path.normpath(path),
            'type': file_type,
            'source_video': video_path,
            'manipulations': str([manip]),
            'name': name_after
        })
    file_after_test = [files for files in project.files if files['name'] == name_after]
    assert (len(file_after_test) == 1)
    project.save()
    return path

def change_origin(project, video_path, origin):
    file = [files for files in project.files if os.path.normpath(files['path']) == os.path.normpath(video_path)]
    assert(len(file) == 1)
    file = file[0]
    index_of_file = project.files.index(file)
    project.files[index_of_file]['origin'] = str(origin)
    project.save()

# Always ensure all reference_frames come first in the list
# def refresh_all_list(project, video_list, indices, last_manips_to_display=['All']):
#     video_list.model().clear()
#     for f in project.files:
#         item = QStandardItem(f['name'])
#         item.setDropEnabled(False)
#         if f['type'] != 'ref_frame':
#             continue
#         video_list.model().appendRow(item)
#     for f in project.files:
#         item = QStandardItem(f['name'])
#         item.setDropEnabled(False)
#         if f['type'] != 'video':
#             continue
#         if 'All' in last_manips_to_display:
#             video_list.model().appendRow(item)
#         elif f['manipulations'] != []:
#             if ast.literal_eval(f['manipulations'])[-1] in last_manips_to_display:
#                 video_list.model().appendRow(item)
#
#     if len(indices) > 1:
#         theQIndexObjects = [video_list.model().createIndex(rowIndex, 0) for rowIndex in
#                             indices]
#         for Qindex in theQIndexObjects:
#             video_list.selectionModel().select(Qindex, QItemSelectionModel.Select)
#     else:
#         video_list.setCurrentIndex(video_list.model().index(indices[0], 0))


def refresh_list(project, ui_list, indices, types=None, last_manips_to_display=None):
    if types:
        ui_list.model().clear()
        for typ in types:
            for f in project.files:
                item = QStandardItem(f['name'])
                item.setDropEnabled(False)
                if f['type'] != typ:
                    continue
                if not last_manips_to_display or 'All' in last_manips_to_display:
                    ui_list.model().appendRow(QStandardItem(item))
                elif f['manipulations'] != []:
                    if ast.literal_eval(f['manipulations'])[-1] in last_manips_to_display:
                        ui_list.model().appendRow(item)

    if len(indices) == 0:
        return
    if len(indices) > 1:
        ui_list.setCurrentIndex(ui_list.model().index(indices[0], 0))
        theQIndexObjects = [ui_list.model().createIndex(rowIndex, 0) for rowIndex in
                            indices]
        for Qindex in theQIndexObjects:
            ui_list.selectionModel().select(Qindex, QItemSelectionModel.Select)
    elif len(indices) == 1:
        ui_list.setCurrentIndex(ui_list.model().index(indices[0], 0))

def refresh_video_list_via_combo_box(widget, list_display_type, trigger_item=None):
    if trigger_item != 0:
        widget.toolbutton.model().item(0, 0).setCheckState(Qt.Unchecked)

    last_manips_to_display = []
    for i in range(widget.toolbutton.count()):
        if widget.toolbutton.model().item(i, 0).checkState() != 0:
            last_manips_to_display = last_manips_to_display + [widget.toolbutton.itemText(i)]
    refresh_list(widget.project, widget.video_list, [0], list_display_type, last_manips_to_display)

def get_project_file_from_key_item(project, key, item):
    file = [files for files in project.files if os.path.normpath(files[key]) == os.path.normpath(item)]
    if not file:
        return
    assert (len(file) == 1)
    return file[0]

def add_combo_dropdown(widget, items):
    widget.ComboBox = CheckableComboBox()
    widget.ComboBox.addItem('All')
    item = widget.ComboBox.model().item(0, 0)
    item.setCheckState(Qt.Checked)
    for i, text in enumerate(items):
        widget.ComboBox.addItem(text)
        item = widget.ComboBox.model().item(i+1, 0)
        item.setCheckState(Qt.Unchecked)
    return widget.ComboBox


def flatten(foo):
    for x in foo:
        if hasattr(x, '__iter__') and not isinstance(x, str):
            for y in flatten(x):
                yield y
        else:
            yield x

#todo: fix toolbutton...
def get_list_of_project_manips(project):
    vid_files = [f for f in project.files if f['type'] in constants.TOOLBUTTON_TYPES]
    list_of_manips = [x['manipulations'] for x in vid_files if x['manipulations'] != []]
    list_of_manips = [ast.literal_eval(l) for l in list_of_manips]
    list_of_manips = list(flatten(list_of_manips))
    return list(set(list_of_manips))


def selected_video_changed_multi(widget, selected, deselected):
    if not widget.video_list.selectedIndexes() or not widget.video_list.currentIndex().data(Qt.DisplayRole):
        return
    # for index in deselected.indexes():
    #     vidpath = str(os.path.join(widget.project.path,
    #                                index.data(Qt.DisplayRole))
    #                   + '.npy')
    #     widget.selected_videos = [x for x in widget.selected_videos if x != vidpath]
    widget.selected_videos = []
    for index in widget.video_list.selectedIndexes():
        vidpath = str(os.path.normpath(os.path.join(widget.project.path, index.data(Qt.DisplayRole)) + '.npy'))
        if vidpath not in widget.selected_videos and vidpath != 'None':
            widget.selected_videos = widget.selected_videos + [vidpath]
            widget.shown_video_path = str(os.path.normpath(os.path.join(widget.project.path,
                                                       widget.video_list.currentIndex().data(Qt.DisplayRole))
                                    + '.npy'))
    frame = load_reference_frame(widget.shown_video_path)
    widget.view.show(frame)


def video_triggered(widget, index, scaling=False):
    filename = str(os.path.join(widget.project.path, index.data(Qt.DisplayRole)) + '.npy')
    dialog = PlayerDialog(widget.project, filename, widget, scaling)
    dialog.show()
    # widget.open_dialogs.append(dialog)

def update_plugin_params(widget, key, val):
    widget.params[key] = val
    widget.project.pipeline[widget.plugin_position] = widget.params
    widget.project.save()

def save_dock_window_to_project(widget, window_type, pickle_path):
    widget.project.files.append({
        'path': pickle_path,
        'type': window_type,
        'name': os.path.basename(pickle_path)
    })
    widget.project.save()

class WrongNumberOfArguments(TypeError):
    print()
    pass

# def setup_and_get_dock_window(widget, video_path_to_plots_dict, DockWindow, state=None):
#     # """One of state or area MUST not be None"""
#     # if not state and not area:
#     #     raise WrongNumberOfArguments()
#     # if not state and area:
#     #     state = area.saveState()
#     main_window = DockWindow(video_path_to_plots_dict, state=state, parent=widget)
#     main_window.resize(2000, 900)
#     main_window.show()
#     widget.open_dialogs.append(main_window)
#     main_window.saving_state[str].connect(functools.partial(save_dock_window_to_project, widget,
#                                                             widget.Labels.window_type))
#     return DockWindow

def save_dock_windows(widget, window_type):
    pass

    # if not widget.open_dialogs:
    #     qtutil.info('No plot windows are open. ')
    #     return
    #
    # continue_msg = "All Windows will be closed after saving, *including* ones you have not saved. \n" \
    #                "\n" \
    #                "Continue?"
    # reply = QMessageBox.question(widget, 'Save All',
    #                              continue_msg, QMessageBox.Yes, QMessageBox.No)
    # if reply == QMessageBox.No:
    #     return
    #
    # qtutil.info('There are ' + str(len(widget.open_dialogs)) + ' plot windows in memory. We will now choose a path to '
    #                                                            'save each one to. Simply don\'t save ones you have '
    #                                                            'purposefully closed. You now have '
    #                                                            'one last chance to save and recover '
    #                                                            'any windows you accidentally closed')
    # for (dialog, video_path_to_plots_dict) in widget.open_dialogs_data_dict:
    #     win_title = dialog.windowTitle()
    #     win_title = win_title[12:len(str(uuid.uuid4())) + 12]
    #     filters = {
    #         '.pkl': 'Python pickle file (*.pkl)'
    #     }
    #     default = win_title
    #     pickle_path = widget.filedialog(default, filters)
    #     if pickle_path:
    #         widget.project.files.append({
    #             'path': pickle_path,
    #             'type': window_type,
    #             'name': os.path.basename(pickle_path)
    #         })
    #         widget.project.save()
    #         # Now save the actual file
    #         # area = dialog.centralWidget()
    #         # state = area.saveState()
    #         try:
    #             with open(pickle_path, 'wb') as output:
    #                 pickle.dump(video_path_to_plots_dict, output, -1)
    #         except:
    #             qtutil.critical(pickle_path + " could not be saved. Ensure MBE has write access to this location and "
    #                                           "that another program isn't using this file.")
    # qtutil.info("All files have been saved")
    #
    # for dialog in widget.open_dialogs:
    #     dialog.close()
    # widget.open_dialogs = []

def load_dock_windows(widget, window_type, DockWindow):
    pass

    # paths = [p['path'] for p in widget.project.files if p['type'] == window_type]
    #
    # if not paths:
    #     qtutil.info("Your project has no windows. Make and save some!")
    #     return
    #
    # for pickle_path in paths:
    #     try:
    #         with open(pickle_path, 'rb') as input:
    #             [video_path_to_plots_dict, state] = pickle.load(input)
    #     except:
    #         del_msg = pickle_path + " could not be loaded. If this file exists, ensure MBE has read access to this " \
    #                                 "location and that another program isn't using this file " \
    #                                 "" \
    #                                 "\n \nOtherwise, would you like to detatch this file from your project? "
    #         reply = QMessageBox.question(widget, 'File Load Error',
    #                                      del_msg, QMessageBox.Yes, QMessageBox.No)
    #         if reply == QMessageBox.Yes:
    #             norm_path = os.path.normpath(pickle_path)
    #             widget.project.files[:] = [f for f in widget.project.files if os.path.normpath(f['path']) != norm_path]
    #             widget.project.save()
    #             load_msg = pickle_path + " detatched from your project." \
    #                                      "" \
    #                                      "\n \n Would you like to continue loading the " \
    #                                      "remaining project windows?"
    #             reply = QMessageBox.question(widget, 'Continue?',
    #                                          load_msg, QMessageBox.Yes, QMessageBox.No)
    #         if reply == QMessageBox.No:
    #             return
    #         continue
    #     DockWindow = setup_and_get_dock_window(widget, video_path_to_plots_dict, DockWindow, state=state)
    #     DockWindow.setWindowTitle(os.path.basename(pickle_path))
        # main_window.resize(2000, 900)
        # widget.plot_to_docks(video_path_to_plots_dict, main_window.area)
        # main_window.show()
        # widget.open_dialogs.append(main_window)
        # widget.open_dialogs_data_dict.append((main_window, video_path_to_plots_dict))