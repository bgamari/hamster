# - coding: utf-8 -
import os, time
import datetime
from os.path import *
import gnomeapplet, gtk
import gtk.glade
import gobject
from pango import ELLIPSIZE_END

from hamster import dispatcher, storage, SHARED_DATA_DIR
import hamster.eds
from hamster.About import show_about
from hamster.overview import DayStore, OverviewController, format_duration

class HamsterEventBox(gtk.EventBox):
    def __init__(self):
        gtk.EventBox.__init__(self)
        self.active = False
        self.set_visible_window(False)
        self.connect('button-press-event', self.on_button_press)
    
    def on_button_press(self, widget, event):
        if event.button == 1:
            self.set_active(not self.active)
            return True
                
    def get_active(self):
        return self.active
    
    def set_active(self, active):
        changed = (self.active != active)
        self.active = active
        
        if changed:
            dispatcher.dispatch('panel_visible', active)

    def activity_updated(self, renames):
        dispatcher.dispatch('activity_updated', renames)

    def fact_updated(self, date = None):
        date = date or datetime.datetime.today()
        dispatcher.dispatch('day_updated', date)


class HamsterApplet(object):
    visible = False # global visibility toggler
    overview = None

    def __init__(self, applet):
        self.applet = applet
        self.label = gtk.Label(_(u"Hamster"))

        # load window of activity switcher and todays view
        self.w_tree = gtk.glade.XML(os.path.join(SHARED_DATA_DIR, "menu.glade"))
        self.w_tree.signal_autoconnect(self)
        self.window = self.w_tree.get_widget('hamster-window')
        self.items = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT)
        activity_list = self.w_tree.get_widget('activity-list')
        activity_list.set_model(self.items)
        activity_list.set_text_column(0)

        # init today's tree
        self.treeview = self.w_tree.get_widget('today')
        self.treeview.set_tooltip_column(1)
        timeColumn = gtk.TreeViewColumn('Time')
        timeColumn.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        timeColumn.set_expand(False)
        timeCell = gtk.CellRendererText()
        timeColumn.pack_start(timeCell, True)
        timeColumn.set_attributes(timeCell, text=2)
        self.treeview.append_column(timeColumn)

        nameColumn = gtk.TreeViewColumn('Name')
        nameColumn.set_expand(True)
        nameCell = gtk.CellRendererText()
        nameCell.set_property('ellipsize', ELLIPSIZE_END)
        nameColumn.pack_start(nameCell, True)
        nameColumn.set_attributes(nameCell, text=1)
        self.treeview.append_column(nameColumn)
        
        durationColumn = gtk.TreeViewColumn(' ')
        durationColumn.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        durationColumn.set_expand(False)
        durationCell = gtk.CellRendererText()
        durationColumn.pack_start(durationCell, True)
        durationColumn.set_attributes(durationCell, text=3)
        self.treeview.append_column(durationColumn)
        
        self.last_activity = None
        
        self.evBox = HamsterEventBox()
        
        self.today = None
        self.update_status()
        self.load_today()

        # add a timer so we can update duration of current task
        # a little naggy, still maybe that will remind user to change tasks
        # we go for refresh each minute
        gobject.timeout_add(60000, self.update_tick)

        # build the menu
        self.refresh_menu()

        self.evBox.add(self.label)

        self.applet.add(self.evBox)

        dispatcher.add_handler('panel_visible', self.__show_toggle)
        dispatcher.add_handler('activity_updated', self.after_activity_update)
        dispatcher.add_handler('day_updated', self.after_fact_update)

        self.applet.setup_menu_from_file (
            SHARED_DATA_DIR, "Hamster_Applet.xml",
            None, [
            ("About", self.on_about),
            ("edit_activities", self.edit_activities),
            ])

        self.applet.show_all()
        self.applet.set_background_widget(self.applet)
    
    def panel_clicked(self):
        self.evBox.set_active(self, not self.evBox.get_active())
    
    def update_tick(self):
        today = datetime.date.today()
        if today != self.today:
            self.load_today()
        if self.last_activity:
            # update end time
            storage.touch_fact(self.last_activity)
        return True

    def update_status(self):
        if self.last_activity:
            delta = datetime.datetime.now() - self.last_activity['start_time']
            duration = delta.seconds /  60
            label = " %s %s" % (self.last_activity['name'], format_duration(duration))
            
            self.w_tree.get_widget('current_activity').set_text(self.last_activity['name'])
            self.w_tree.get_widget('stop_tracking').set_sensitive(1);
        else:
            label = " %s" % _(u"No activity")
            self.w_tree.get_widget('stop_tracking').set_sensitive(0);
        self.label.set_text(label)
        
    def load_today(self):
        """sets up today's tree and fills it with records
           returns information about last activity"""

        treeview = self.w_tree.get_widget('today')
        self.today = datetime.date.today()
        day = DayStore(self.today);
        treeview.set_model(day.fact_store)

    def refresh_menu(self):
        activity_list = self.w_tree.get_widget('activity-list')
        store = activity_list.get_model()
        store.clear()

        #populate fresh list from DB
        activities = storage.get_activity_list()
        prev_item = None

        today = datetime.date.today()
        for activity in activities:
            item = store.append([activity['name'], activity['id']])
            #set selected
            if self.last_activity and activity['name'] == self.last_activity['name']:
                activity_list.set_active_iter(item)

        tasks = hamster.eds.get_eds_tasks()
        for activity in tasks:
            item = store.append([activity['name'], -1])

        return True
    
    def on_stop_tracking(self, button):
        storage.touch_fact(self.last_activity)
        self.last_activity = None
        self.update_status()
        self.evBox.fact_updated()
        self.evBox.set_active(False)
        
    def on_about (self, component, verb):
        show_about(self.applet)

    def activity_changed(self, component):
        # do stuff only if user has selected something
        # for other cases activity_edited will be triggered
        if component.get_active_iter():
            self.activity_edited(component.child) # forward

    def activity_edited(self, component):
        activity_name = component.get_text()
        self.last_activity = storage.add_fact(activity_name)
        self.update_status() # dispatch comes before assignment
        self.evBox.set_active(False)

    def edit_activities(self, menu_item, verb):
        self.set_active_main(False)
        
        from hamster.activities import ActivitiesEditor
        activities_editor = ActivitiesEditor(self.evBox)

        activities_editor.show()

    def after_activity_update(self, widget, renames):
        print "activities updated"
        self.refresh_menu()
        if renames:
            print "something renamed"
            self.load_today()
            self.update_status()
    
    def after_fact_update(self, event, date):
        print "fact updated"

        if date.date() == datetime.date.today():
            print "Fact of today updated"
            self.load_today()
            self.update_status()
    
    def show_overview(self, menu_item):
        self.set_active_main(False)
        overview = OverviewController(self.evBox)
        overview.show()

    def after_fact_changes(self, some_object):
        self.load_today()

    def __show_toggle(self, event, is_active):
        if not is_active:
            self.window.hide()
            return

        self.window.show_all()

        label_geom = self.label.get_allocation()
        window_geom = self.window.get_allocation()
        x, y = gtk.gdk.Window.get_origin(self.label.window)

        self.popup_dir = self.applet.get_orient()

        if self.popup_dir in [gnomeapplet.ORIENT_DOWN]:
            y = y + label_geom.height + 6;
        elif self.popup_dir in [gnomeapplet.ORIENT_UP]:
            y = y - window_geom.height - 6;
        
        x = x - 6 #temporary position fix. TODO - replace label with a toggle button
        
        self.window.move(x, y)
        a_list = self.w_tree.get_widget('activity-list')
        a_list.child.select_region(0, -1)
        a_list.grab_focus()
            
    def get_active_main (self):
        return self.evBox.get_active ()
    
    def set_active_main (self, is_active):
        self.evBox.set_active (is_active)
             

