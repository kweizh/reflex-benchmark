You are tasked with extending the Reflex UI by adding a specialized third-party color picker that is not available in the native Reflex component library.

You need to create a custom Reflex component wrapper for the `react-colorful` npm package (specifically the `HexColorPicker` tag) by subclassing the appropriate component base class.

**Constraints:**
- You MUST subclass `NoSSRComponent` to bypass server-side rendering issues for this React library.
- You must properly define the `library` and `tag` class attributes for the npm package.
- You must define an `on_change` event trigger using `rx.EventHandler[lambda color: [color]]` to properly serialize the callback arguments back to the Reflex state.