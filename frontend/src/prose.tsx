import Markdown from "react-markdown";
import gfm from "remark-gfm";
import math from "remark-math";
import katex from "rehype-katex";
import highlight from "rehype-highlight";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";
export function Prose({ text }: { text: string }) {
  if (/^\s*\d+[.)]\s*$/.test(text)) return <p>{text}</p>;
  return (
    <Markdown
      remarkPlugins={[gfm, math]}
      rehypePlugins={[katex, highlight]}
      skipHtml
      components={{
        img: ({ alt }) => <span>[Image: {alt}]</span>,
        a: ({ href, children }) => (
          <a
            href={href && /^https?:\/\//.test(href) ? href : undefined}
            rel="noopener noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
      }}
    >
      {text}
    </Markdown>
  );
}
