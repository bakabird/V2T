module.exports = {
    apps: [{
        name: "v2t-webui",
        script: "webui.py",
        interpreter: "python",
        cwd: __dirname,

        // 自动重启配置
        autorestart: true,
        max_restarts: 10,
        restart_delay: 3000,

        // 不监视文件变化
        watch: false,

        // 日志配置
        log_date_format: "YYYY-MM-DD HH:mm:ss",
        error_file: "./logs/webui-error.log",
        out_file: "./logs/webui-out.log",
        merge_logs: true,

        // 环境变量
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }]
};
