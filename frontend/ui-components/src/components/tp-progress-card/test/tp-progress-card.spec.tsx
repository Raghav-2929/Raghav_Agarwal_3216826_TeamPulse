import { newSpecPage } from '@stencil/core/testing';
import { TpProgressCard } from '../tp-progress-card';

describe('tp-progress-card', () => {
  it('renders heading, category, figures and streak', async () => {
    const page = await newSpecPage({
      components: [TpProgressCard],
      html: `<tp-progress-card heading="Morning run" category="fitness" value="3" target="5" unit="runs" streak="4"></tp-progress-card>`,
    });
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('.heading')!.textContent).toBe('Morning run');
    expect(root.querySelector('.category')!.textContent).toBe('Fitness');
    expect(root.querySelector('.figures')!.textContent).toContain('3');
    expect(root.querySelector('.figures')!.textContent).toContain('/ 5 runs');
    expect(root.querySelector('[role="progressbar"]')!.getAttribute('aria-valuenow')).toBe('3');
    expect(root.querySelector('.streak')!.textContent).toContain('4-day streak');
    expect(root.querySelector('.fill')!.getAttribute('style')).toContain('width: 60%');
  });

  it('hides the meter without a target and the footer without actions', async () => {
    const page = await newSpecPage({
      components: [TpProgressCard],
      html: `<tp-progress-card heading="Read"></tp-progress-card>`,
    });
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('.progress')).toBeNull();
    expect(root.querySelector('.actions')!.classList.contains('hidden')).toBe(true);
    expect(root.querySelector('.streak')).toBeNull();
  });

  it('emits tp-action when the built-in button is clicked', async () => {
    const page = await newSpecPage({
      components: [TpProgressCard],
      html: `<tp-progress-card heading="Meditate" action-label="Mark complete"></tp-progress-card>`,
    });
    const spy = jest.fn();
    page.root!.addEventListener('tp-action', spy);
    const button = page.root!.shadowRoot!.querySelector('button')!;
    expect(button.textContent).toBe('Mark complete');
    button.click();
    await page.waitForChanges();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].detail).toEqual({ action: 'complete' });
  });

  it('disables the action and shows the completed state', async () => {
    const page = await newSpecPage({
      components: [TpProgressCard],
      html: `<tp-progress-card heading="Meditate" action-label="Mark complete" completed></tp-progress-card>`,
    });
    const spy = jest.fn();
    page.root!.addEventListener('tp-action', spy);
    const button = page.root!.shadowRoot!.querySelector('button')!;
    expect(button.hasAttribute('disabled')).toBe(true);
    expect(button.textContent).toContain('Done');
    expect(page.root!.shadowRoot!.querySelector('.status')!.textContent).toContain('Completed');
    expect(page.root!.hasAttribute('completed')).toBe(true);
    button.click();
    expect(spy).not.toHaveBeenCalled();
  });

  it('renders the footer for slotted actions', async () => {
    const page = await newSpecPage({
      components: [TpProgressCard],
      html: `<tp-progress-card heading="Hydrate"><a slot="actions" href="/habits/1">Details</a></tp-progress-card>`,
    });
    expect(page.root!.shadowRoot!.querySelector('.actions slot[name="actions"]')).not.toBeNull();
    expect(page.root!.shadowRoot!.querySelector('.actions')!.classList.contains('hidden')).toBe(false);
  });

  it('shows the footer when actions are slotted after the first render', async () => {
    const page = await newSpecPage({ components: [TpProgressCard], html: `<tp-progress-card heading="Hydrate"></tp-progress-card>` });
    const footer = () => page.root!.shadowRoot!.querySelector('.actions')!;
    expect(footer().classList.contains('hidden')).toBe(true);
    const link = page.doc.createElement('a');
    link.setAttribute('slot', 'actions');
    link.textContent = 'Details';
    page.root!.appendChild(link);
    page.root!.shadowRoot!.querySelector('slot[name="actions"]')!.dispatchEvent(new Event('slotchange'));
    await page.waitForChanges();
    expect(footer().classList.contains('hidden')).toBe(false);
  });
});
