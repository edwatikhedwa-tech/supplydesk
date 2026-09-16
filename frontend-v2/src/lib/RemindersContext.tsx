import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from './api';
import type { NotificationSettings, ReminderAlert } from './types';

const POLL_INTERVAL_MS = 45_000;

interface RemindersState {
  /** Currently active (`triggered`, undone) reminders -- the toast + badge source. */
  active: ReminderAlert[];
  /** Recently triggered/dismissed reminders for the Notification Center. */
  feed: ReminderAlert[];
  settings: NotificationSettings;
  loaded: boolean;
  /** Bumped whenever a reminder action changes task data (complete/snooze) --
   * consumers with their own independent task fetch (Dashboard, TasksSection,
   * DashboardCalendar) put this in their reload dependency array so a task
   * completed from a toast or the Notification Center is reflected without
   * a page reload, the same pattern used for the supplier-contacts refresh
   * link in Messages.tsx/SupplierCardPanel. */
  taskDataVersion: number;
  reload: () => void;
  complete: (taskId: number, reminderId: number) => Promise<void>;
  dismiss: (reminderId: number) => Promise<void>;
  snooze: (reminderId: number, input: { minutes?: number; until?: string; timezone?: string }) => Promise<void>;
  markRead: (reminderId: number) => Promise<void>;
  markAllRead: () => Promise<void>;
  updateSettings: (next: NotificationSettings) => Promise<void>;
}

const RemindersContext = createContext<RemindersState | null>(null);

export function RemindersProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ReminderAlert[]>([]);
  const [feed, setFeed] = useState<ReminderAlert[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [taskDataVersion, setTaskDataVersion] = useState(0);
  const [settings, setSettings] = useState<NotificationSettings>({
    sound_enabled: true, browser_notifications_enabled: false, default_reminder_offset_minutes: 0,
  });

  const refreshActive = useCallback(async () => {
    try {
      const result = await api.listDueReminders();
      setActive(result.items);
      setLoaded(true);
    } catch {
      // A failed poll keeps the previous (already-shown) state instead of
      // clearing live toasts on a transient network blip.
    }
  }, []);

  const refreshFeed = useCallback(async () => {
    try {
      const result = await api.listNotificationFeed();
      setFeed(result.items);
    } catch {
      // Same as above: keep showing the last known feed.
    }
  }, []);

  const reload = useCallback(() => {
    void refreshActive();
    void refreshFeed();
  }, [refreshActive, refreshFeed]);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    reload();
    void api.getNotificationSettings().then(setSettings).catch(() => undefined);
    intervalRef.current = setInterval(reload, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reload]);

  const complete = useCallback(async (taskId: number, _reminderId: number) => {
    await api.setTaskDone(taskId, true);
    reload();
    setTaskDataVersion((v) => v + 1);
  }, [reload]);

  const dismiss = useCallback(async (reminderId: number) => {
    await api.dismissReminder(reminderId);
    reload();
  }, [reload]);

  const snooze = useCallback(async (reminderId: number, input: { minutes?: number; until?: string; timezone?: string }) => {
    await api.snoozeReminder(reminderId, input);
    reload();
    setTaskDataVersion((v) => v + 1);
  }, [reload]);

  const markRead = useCallback(async (reminderId: number) => {
    await api.markReminderRead(reminderId);
    void refreshFeed();
  }, [refreshFeed]);

  const markAllRead = useCallback(async () => {
    await api.markAllRemindersRead();
    void refreshFeed();
  }, [refreshFeed]);

  const updateSettings = useCallback(async (next: NotificationSettings) => {
    const result = await api.setNotificationSettings(next);
    setSettings({ sound_enabled: result.sound_enabled, browser_notifications_enabled: result.browser_notifications_enabled, default_reminder_offset_minutes: result.default_reminder_offset_minutes });
  }, []);

  return (
    <RemindersContext.Provider value={{ active, feed, settings, loaded, taskDataVersion, reload, complete, dismiss, snooze, markRead, markAllRead, updateSettings }}>
      {children}
    </RemindersContext.Provider>
  );
}

export function useReminders(): RemindersState {
  const ctx = useContext(RemindersContext);
  if (!ctx) throw new Error('useReminders must be used within RemindersProvider');
  return ctx;
}
