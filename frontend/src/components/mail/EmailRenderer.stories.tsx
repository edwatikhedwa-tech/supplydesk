import type { Meta, StoryObj } from '@storybook/react';
import { EmailRenderer } from './EmailRenderer';

const meta = {
  title: 'Mail/EmailRenderer',
  component: EmailRenderer,
  parameters: {
    layout: 'padded',
  },
  args: {
    className: 'max-w-2xl rounded-xl border border-ink-200 bg-white p-4 text-ink-900',
    text: null,
  },
} satisfies Meta<typeof EmailRenderer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const PlainText: Story = {
  args: {
    html: null,
    text: 'Здравствуйте!\n\nЭто обычное текстовое письмо.\n\nС уважением, команда SupplyDesk.',
  },
};

export const RichHtml: Story = {
  args: {
    html: `
      <table role="presentation" width="640" style="width:640px;max-width:100%;background:#f6f8fb;border-radius:12px;">
        <tr><td style="padding:24px;">
          <h1>Обновление по заявке #1055</h1>
          <p>Поставщик подтвердил наличие позиции и готов отправить предложение.</p>
          <p><a href="https://example.com/request/1055">Открыть заявку</a></p>
        </td></tr>
      </table>
    `,
    text: null,
  },
};

export const OriginalLayout: Story = {
  args: {
    html: `
      <style>
        .email-page { background:#f3f6fa; }
        .email-card { border-radius:24px; }
        .email-card-blue { background:#1478f2; color:#fff; }
        .email-card-pale { background:#cfe5ff; color:#1f2937; }
        .email-button { background:#17191c; color:#fff; border-radius:12px; text-decoration:none; }
        @media (max-width: 600px) {
          .email-page td.email-shell { padding:16px !important; }
          .email-card td.email-card-content { padding:20px !important; }
        }
      </style>
      <table class="email-page" role="presentation" align="center" width="640" style="width:640px;max-width:100%;margin:0 auto;background:#f3f6fa;border-radius:16px;">
        <tr><td class="email-shell" style="padding:32px;">
          <table class="email-card email-card-pale" role="presentation" width="100%" style="width:100%;margin:0 0 20px;background:#cfe5ff;border-radius:24px;">
            <tr><td class="email-card-content" style="padding:26px 28px;color:#1f2937;">
              <p style="margin:0 0 12px;font-size:16px;line-height:1.45;">Это сервисы для повседневных задач. Расскажем о главных возможностях.</p>
            </td></tr>
          </table>
          <table class="email-card email-card-blue" role="presentation" width="100%" style="width:100%;margin:0 0 20px;background:#1478f2;border-radius:24px;">
            <tr><td class="email-card-content" style="padding:28px;color:#fff;">
              <h1 style="margin:0 0 12px;font-size:28px;line-height:1.1;font-weight:500;">ПИСЬМА ИЗ ВСЕХ СЕРВИСОВ — В ПОЧТЕ</h1>
              <p style="margin:0 0 20px;font-size:16px;line-height:1.35;">Соберите всё из разных ящиков, чтобы не переключаться между приложениями.</p>
              <a class="email-button" href="https://example.com/collect" style="display:inline-block;padding:13px 20px;background:#17191c;color:#fff;border-radius:12px;text-decoration:none;">Собрать письма</a>
            </td></tr>
          </table>
          <table class="email-card email-card-pale" role="presentation" width="100%" style="width:100%;margin:0 0 20px;background:#cfe5ff;border-radius:24px;">
            <tr><td class="email-card-content" style="padding:26px 28px;color:#1f2937;">
              <h2 style="margin:0 0 12px;font-size:24px;line-height:1.15;font-weight:500;">Настройте рабочий день под себя</h2>
              <a class="email-button" href="https://example.com/customize" style="display:inline-block;padding:13px 20px;background:#17191c;color:#fff;border-radius:12px;text-decoration:none;">Настроить</a>
            </td></tr>
          </table>
          <p style="margin:28px 0 0;color:#4b5563;font-size:15px;line-height:1.5;">Делимся важным, команда Mail</p>
        </td></tr>
      </table>
    `,
    text: null,
  },
};

export const RemoteImagesBlocked: Story = {
  args: {
    html: `
      <h2>Письмо с внешними изображениями</h2>
      <p>Изображение не должно оставлять пустой блок в содержимом.</p>
      <img data-remote-src="https://example.com/tracker.gif" width="600" height="400" alt="Трекер">
      <p>Текст после скрытого изображения остаётся доступным для чтения.</p>
    `,
    text: null,
    hasRemoteImages: true,
  },
};

export const CidImage: Story = {
  args: {
    html: `
      <h2>CID-изображение</h2>
      <p>Текст письма должен отображаться рядом со встроенной картинкой.</p>
      <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=" width="160" height="80" alt="Тестовое CID-изображение">
      <p>Внешних картинок в этом письме нет.</p>
    `,
    text: null,
    hasRemoteImages: false,
  },
};

export const MarketingSpacerCleanup: Story = {
  args: {
    html: `
      <div style="height:220px;padding:90px 0"></div>
      <p>Основной текст письма должен начинаться без большого пустого блока.</p>
      <img data-remote-src="https://example.com/tracker.gif" width="600" height="500" alt="Трекер">
      <div style="min-height:180px;height:180px"></div>
      <p>Текст после удалённого изображения остаётся доступным.</p>
    `,
    text: null,
    hasRemoteImages: true,
  },
};
