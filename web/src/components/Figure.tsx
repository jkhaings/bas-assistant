type Props = { src: string; alt: string; caption?: string };

// Screenshots for long-form pages live in web/public/img/ and are referenced as /img/<name>.png.
export function Figure({ src, alt, caption }: Props) {
    return (
        <figure className="my-6">
            <img
                src={src}
                alt={alt}
                loading="lazy"
                className="w-full rounded-lg border border-stone-200 bg-white"
            />
            {caption && (
                <figcaption className="mt-2 text-center text-sm text-stone-500">
                    {caption}
                </figcaption>
            )}
        </figure>
    );
}
