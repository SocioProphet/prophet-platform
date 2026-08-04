// Mail store — ported from app-vue into the cockpit. Drives the Imbox/Feed/Screener inbox
// over the shared mailApi (on-device bridge; fails honestly via `error`). Optimistic replies.
import { defineStore } from 'pinia';
import * as mailApi from '../services/mailApi';
import type { MailView, Thread, ScreenerItem, ThreadAction } from '../services/mailApi';

export const useMail = defineStore('mail', {
  state: () => ({
    view: 'imbox' as MailView,
    threads: [] as Thread[],
    current: null as Thread | null,
    screener: [] as ScreenerItem[],
    loading: false,
    error: '',
    aiSummary: '',
    paletteOpen: false,
    screenerOpen: false,
    composeOpen: false,
  }),
  getters: {
    replyLaterCount: (s) => s.threads.filter((t) => t.replyLaterAt).length,
    unreadCount: (s) => s.threads.filter((t) => t.unread).length,
  },
  actions: {
    async load(view?: MailView) {
      if (view) this.view = view;
      this.loading = true;
      this.error = '';
      try {
        this.threads = await mailApi.listThreads(this.view);
        if (this.threads.length) await this.select(this.threads[0].id);
        else this.current = null;
      } catch (e: any) {
        this.error = e?.message ?? 'failed to load mail';
      } finally {
        this.loading = false;
      }
    },
    async select(id: string) {
      try {
        this.current = await mailApi.getThread(id);
        const t = this.threads.find((x) => x.id === id);
        if (t) t.unread = false;
        this.aiSummary = '';
        mailApi.aiSummary(id).then((s) => { if (this.current?.id === id) this.aiSummary = s; }).catch(() => {});
      } catch (e: any) {
        this.error = e?.message ?? 'failed to open thread';
      }
    },
    selectRelative(delta: number) {
      if (!this.threads.length) return;
      const idx = Math.max(0, this.threads.findIndex((t) => t.id === this.current?.id));
      const next = this.threads[Math.min(this.threads.length - 1, Math.max(0, idx + delta))];
      if (next) void this.select(next.id);
    },
    async act(action: ThreadAction, opts?: { until?: string }) {
      const id = this.current?.id;
      if (!id) return;
      try {
        await mailApi.threadAction(id, action, opts);
        if (action === 'done' || action === 'setAside') {
          this.threads = this.threads.filter((t) => t.id !== id);
          if (this.threads.length) await this.select(this.threads[0].id); else this.current = null;
        } else if (action === 'replyLater') {
          const t = this.threads.find((x) => x.id === id);
          if (t) t.replyLaterAt = opts?.until ?? 'later';
        }
      } catch (e: any) {
        this.error = e?.message ?? 'action failed';
      }
    },
    async loadScreener() {
      try { this.screener = await mailApi.listScreener(); } catch (e: any) { this.error = e?.message ?? 'screener failed'; }
    },
    async screen(id: string, decision: 'approve' | 'deny') {
      try {
        await mailApi.screenerDecision(id, decision);
        this.screener = this.screener.filter((s) => s.id !== id);
      } catch (e: any) { this.error = e?.message ?? 'screener action failed'; }
    },
    // Reply to the open thread; optimistically append so the pane updates immediately.
    async replyToCurrent(body: string): Promise<void> {
      const thread = this.current;
      if (!thread || !body.trim()) return;
      try {
        await mailApi.sendMail({ to: thread.fromEmail, subject: `Re: ${thread.subject}`, body, inReplyTo: thread.id });
        this.error = '';
        thread.messages = [...(thread.messages ?? []), { id: `local-${Date.now()}`, from: 'You', fromEmail: '', ts: 'now', bodyText: body }];
      } catch (e: any) {
        this.error = e?.message ?? 'reply failed';
        throw e;
      }
    },
    async sendNew(p: { to: string; subject: string; body: string }): Promise<boolean> {
      if (!p.to.trim() || !p.subject.trim()) { this.error = 'to and subject are required'; return false; }
      try { await mailApi.sendMail(p); this.error = ''; return true; }
      catch (e: any) { this.error = e?.message ?? 'send failed'; return false; }
    },
    async draftReply(intent: string): Promise<string> {
      const thread = this.current;
      if (!thread) return '';
      try { return await mailApi.aiDraft(thread.id, intent); }
      catch (e: any) { this.error = e?.message ?? 'draft failed'; return ''; }
    },
  },
});
