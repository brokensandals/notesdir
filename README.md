# notesdir

## File Type Support

<table>
    <thead>
        <tr>
            <th>Type</th>
            <th>Metadata</th>
            <th>Linking</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Markdown</td>
            <td>
                <ul>
                    <li>
                        (optional) YAML metadata block:
                        <ul>
                            <li><code>title</code> (string)</li>
                            <li><code>created</code> (date)</li>
                            <li><code>keywords</code> (array of strings)</li>
                        </ul>
                    </li>
                    <li>Hashtags in the text are also interpreted as tags (in addition to the keywords).</li>
                </ul>
            </td>
            <td>
                Links of the style <code>[text](path)</code> and <code>[text]: path</code> will be updated when files are moved.
            </td>
        </tr>
        <tr>
            <td>HTML</td>
            <td>
                <ul>
                    <li>(optional) <code>title</code> element</li>
                    <li>(optional) <code>meta name="created"</code> element</li>
                    <li>(optional) <code>meta name="keywords"</code> element</li>
                    <li>Hashtags in the text are also interpreted as tags (in addition to the keywords).</li>
                </ul>
            </td>
            <td>
                Links in the <code>href</code> attribute of <code>a</code> elements or the <code>src</code> attribute of various elements will be updated when files are moved. Links in the <code>srcset</code> attribute or in CSS are currently ignored.
            </td>
        </tr>
        <tr>
            <td>PDF</td>
            <td>
                <li>
                    (optional) document info metadata:
                    <ul>
                        <li><code>/Title</code></li>
                        <li><code>/CreationDate</code></li>
                        <li><code>/Keywords</code> (comma-separated)</li>
                    </ul>
                </li>
            </td>
            <td>
                Links in PDF documents are not currently updated.
            </td>
        </tr>
    </tbody>
</table>
