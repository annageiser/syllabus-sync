import React, { useCallback, useState } from 'react';
import { Upload, FileText, CheckCircle2 } from 'lucide-react';

interface FileUploaderProps {
    onFileUpload: (file: File) => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({ onFileUpload }) => {
    const [isDragging, setIsDragging] = useState(false);
    const [fileName, setFileName] = useState<string | null>(null);

    const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            setFileName(file.name);
            onFileUpload(file);
        }
    }, [onFileUpload]);

    const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setFileName(file.name);
            onFileUpload(file);
        }
    };

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            document.getElementById('file-upload')?.click();
        }
    }, []);

    const handleClick = useCallback(() => {
        document.getElementById('file-upload')?.click();
    }, []);

    return (
        <div
            id="drop-zone"
            className={`glass p-12 text-center transition-all duration-300 cursor-pointer border-2 border-dashed ${isDragging
                ? 'border-indigo-400 bg-indigo-500/10 scale-[1.02] shadow-[0_0_30px_rgba(99,102,241,0.3)]'
                : 'border-slate-500/20 hover:border-indigo-500/50'
                }`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onKeyDown={handleKeyDown}
            onClick={handleClick}
            tabIndex={0}
            role="button"
            aria-label="Upload syllabus file"
            aria-describedby="upload-description"
        >
            <input
                type="file"
                className="hidden"
                id="file-upload"
                onChange={handleChange}
                accept=".pdf,.xlsx,.xls,.docx,.html,.htm"
                onClick={(e) => e.stopPropagation()}
            />
            <label htmlFor="file-upload" className="cursor-pointer block" onClick={(e) => e.stopPropagation()}>
                <div className="relative inline-block mb-6">
                    <div className="absolute inset-0 bg-indigo-500 blur-3xl opacity-20 animate-pulse"></div>
                    {fileName ? (
                        <CheckCircle2 className="relative h-20 w-20 text-emerald-500 mx-auto" />
                    ) : (
                        <Upload className="relative h-20 w-20 text-indigo-500 mx-auto" />
                    )}
                </div>

                <h3 className="text-3xl font-black mb-3">
                    {fileName ? 'Ready for Extraction' : 'Smart Syllabus Upload'}
                </h3>
                <p id="upload-description" className="text-slate-500 mb-8 max-w-sm mx-auto font-medium">
                    {fileName ? fileName : 'Drag and drop your academic schedule here. Supporting PDF, Excel, and Word files.'}
                </p>

                <div className="inline-flex items-center px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white font-black rounded-2xl transition-all shadow-xl hover:shadow-indigo-500/30">
                    <FileText className="mr-3 h-6 w-6" />
                    Select Document
                </div>
            </label>
        </div>
    );
};

export default FileUploader;
