from __future__ import annotations


def run_approval_ui(runtime, poll_ms: int = 2000):
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except Exception as exc:
        raise RuntimeError('Tkinter is required for the native approval window.') from exc

    root=tk.Tk(); root.title('Living Assistant Approvals'); root.geometry('760x440')
    frame=ttk.Frame(root,padding=12); frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Pending approvals',font=('TkDefaultFont',14,'bold')).pack(anchor='w')
    lst=tk.Listbox(frame,height=10); lst.pack(fill='x',pady=(8,8))
    detail=tk.Text(frame,height=10,wrap='word'); detail.pack(fill='both',expand=True)
    buttons=ttk.Frame(frame); buttons.pack(fill='x',pady=(8,0))
    current=[]

    def selected():
        sel=lst.curselection(); return current[sel[0]] if sel else None
    def show_detail(_evt=None):
        item=selected(); detail.delete('1.0','end')
        if item: detail.insert('1.0',f"Type: {item.get('kind')}\nAction: {item.get('action')}\nReason: {item.get('reason')}\nCreated: {item.get('created_at')}\nID: {item.get('id')}")
    def decide(value: bool):
        item=selected()
        if not item: return
        if value or messagebox.askyesno('Deny approval','Deny this request?'):
            runtime.approvals.resolve(item['id'],value); refresh()
    def refresh():
        nonlocal current
        current=runtime.approvals.list(status='pending',limit=100)
        selected_id=selected().get('id') if selected() else None
        lst.delete(0,'end')
        for x in current: lst.insert('end',f"[{x.get('kind')}] {x.get('action','')[:100]}")
        if current:
            idx=next((i for i,x in enumerate(current) if x.get('id')==selected_id),0); lst.selection_set(idx); show_detail()
        else:
            detail.delete('1.0','end'); detail.insert('1.0','No pending approvals.')
        root.after(max(1000,poll_ms),refresh)
    ttk.Button(buttons,text='Approve once',command=lambda:decide(True)).pack(side='left')
    ttk.Button(buttons,text='Deny',command=lambda:decide(False)).pack(side='left',padx=8)
    ttk.Button(buttons,text='Refresh',command=refresh).pack(side='right')
    lst.bind('<<ListboxSelect>>',show_detail); refresh(); root.mainloop()
